import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { api, ApiError, type ChapterDetail, type RevisionConflictDetail } from '@/lib/api';

type SaveState = 'saved' | 'saving' | 'dirty' | 'error' | 'conflict';

type RecoveryDraft = {
  version: 1;
  projectId: number;
  chapterId: number;
  baseRevision: number;
  editSequence: number;
  text: string;
  updatedAt: number;
};

type ConflictState = {
  message: string;
  currentRevision: number | null;
  localText: string;
  serverText: string | null;
  serverRevision: number | null;
};

type RecoveryState = {
  kind: 'restored' | 'mismatch';
  message: string;
  localText: string;
  serverText: string;
  baseRevision: number;
  serverRevision: number;
};

export type ManuscriptSnapshot = {
  projectId: number;
  chapterId: number;
  text: string;
  serverRevision: number;
  saveState: SaveState;
  errorMessage: string | null;
  storageError: string | null;
  conflict: ConflictState | null;
  recovery: RecoveryState | null;
  recoveryActionPending: boolean;
  hasUnsaved: boolean;
  isFlushing: boolean;
};

type Listener = () => void;
type AckListener = (detail: ChapterDetail) => void;

type WriteResult = {
  detail: ChapterDetail;
};

export type ManuscriptReplacementToken = {
  projectId: number;
  chapterId: number;
  editSequence: number;
  text: string;
  serverRevision: number;
};

const DRAFT_PREFIX = 'jippeel:manuscript-draft:v1:';
const DEBOUNCE_MS = 1500;

function keyFor(projectId: number, chapterId: number) {
  return `${projectId}:${chapterId}`;
}

function storageKey(projectId: number, chapterId: number) {
  return `${DRAFT_PREFIX}${projectId}:${chapterId}`;
}

function isBrowser() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

function conflictDetail(error: unknown): RevisionConflictDetail | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null;
  const detail = error.detail;
  if (detail && typeof detail === 'object') return detail as RevisionConflictDetail;
  return { message: error.message };
}

function apiMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  return '원고 저장에 실패했습니다.';
}

class ManuscriptDraftCoordinator {
  readonly projectId: number;
  readonly chapterId: number;
  private listeners = new Set<Listener>();
  private ackListeners = new Set<AckListener>();
  private timer: number | undefined;
  private inFlight: Promise<WriteResult> | null = null;
  private inFlightSeq: number | null = null;
  private inFlightText: string | null = null;
  private initialized = false;
  private recoveryActionId = 0;

  text = '';
  serverText = '';
  serverRevision = 0;
  editSequence = 0;
  savedSequence = 0;
  saveState: SaveState = 'saved';
  errorMessage: string | null = null;
  storageError: string | null = null;
  conflict: ConflictState | null = null;
  recovery: RecoveryState | null = null;
  recoveryActionPending = false;
  isFlushing = false;

  constructor(projectId: number, chapterId: number) {
    this.projectId = projectId;
    this.chapterId = chapterId;
    this.snapshotCache = this.makeSnapshot();
  }

  private snapshotCache: ManuscriptSnapshot;

  getSnapshot = (): ManuscriptSnapshot => this.snapshotCache;

  private makeSnapshot(): ManuscriptSnapshot {
    return {
      projectId: this.projectId,
      chapterId: this.chapterId,
      text: this.text,
      serverRevision: this.serverRevision,
      saveState: this.saveState,
      errorMessage: this.errorMessage,
      storageError: this.storageError,
      conflict: this.conflict,
      recovery: this.recovery,
      recoveryActionPending: this.recoveryActionPending,
      hasUnsaved: this.hasUnsaved(),
      isFlushing: this.isFlushing,
    };
  }

  subscribe = (listener: Listener) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  onAck(listener: AckListener) {
    this.ackListeners.add(listener);
    return () => { this.ackListeners.delete(listener); };
  }

  private emit() {
    this.snapshotCache = this.makeSnapshot();
    for (const listener of this.listeners) listener();
  }

  private emitAck(detail: ChapterDetail) {
    for (const listener of this.ackListeners) listener(detail);
  }

  private unresolvedRecovery() {
    return this.recovery?.kind === 'mismatch';
  }

  private unresolvedRecoveryMessage() {
    return '로컬 복구본과 서버 원고가 다릅니다. 로컬 복구본을 먼저 선택하거나 서버 원고로 계속할지 정하세요.';
  }

  initFromServer(detail: ChapterDetail, force = false) {
    if (detail.id !== this.chapterId || detail.project_id !== this.projectId) return;
    const serverRevision = detail.revision ?? 0;
    if (force) {
      this.initialized = true;
      this.serverRevision = serverRevision;
      this.serverText = detail.content_md;
      this.text = detail.content_md;
      this.editSequence += 1;
      this.savedSequence = this.editSequence;
      this.saveState = 'saved';
      this.errorMessage = null;
      this.conflict = null;
      this.recovery = null;
      this.removeStoredDraft();
      this.emit();
      return;
    }

    if (!this.initialized) {
      this.initialized = true;
      this.serverRevision = serverRevision;
      this.serverText = detail.content_md;
      this.text = detail.content_md;
      this.savedSequence = this.editSequence;
      this.saveState = 'saved';
      this.errorMessage = null;
      this.loadRecovery(detail);
      this.emit();
      return;
    }

    const sentTextMatches = this.inFlightText !== null && detail.content_md === this.inFlightText;
    if (sentTextMatches) {
      this.acknowledge(detail, this.inFlightSeq ?? this.editSequence, this.inFlightText ?? detail.content_md);
      return;
    }

    this.serverRevision = serverRevision;
    this.serverText = detail.content_md;
    if (this.unresolvedRecovery()) {
      this.recovery = { ...this.recovery!, serverText: detail.content_md, serverRevision };
      this.saveState = 'conflict';
      this.errorMessage = null;
      this.emit();
      return;
    }
    if (!this.hasUnsaved() && this.saveState !== 'saving') {
      this.text = detail.content_md;
      this.savedSequence = this.editSequence;
      this.saveState = 'saved';
      this.errorMessage = null;
    }
    this.emit();
  }

  edit(text: string) {
    if (this.unresolvedRecovery()) {
      this.saveState = 'conflict';
      this.errorMessage = this.unresolvedRecoveryMessage();
      this.emit();
      return;
    }
    this.text = text;
    this.editSequence += 1;
    this.errorMessage = null;
    if (!this.conflict) this.saveState = text === this.serverText ? 'saved' : 'dirty';
    this.persistDraft();
    this.emit();
    if (!this.conflict) this.scheduleSave();
  }

  scheduleSave() {
    if (typeof window === 'undefined') return;
    window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => void this.flush(), DEBOUNCE_MS);
  }

  async clearRecovery() {
    if (this.recoveryActionPending) return;
    const recovery = this.recovery;
    if (recovery?.kind === 'mismatch') {
      const refreshed = await this.refreshRecoveryServerText();
      if (!refreshed || !this.unresolvedRecovery()) return;
      const latest = this.recovery!;
      this.recoveryActionId += 1;
      this.recoveryActionPending = false;
      this.serverRevision = latest.serverRevision;
      this.serverText = latest.serverText;
      this.text = latest.serverText;
      this.editSequence += 1;
      this.savedSequence = this.editSequence;
      this.conflict = null;
      this.recovery = null;
      this.saveState = 'saved';
      this.errorMessage = null;
      this.removeStoredDraft();
      this.emit();
      return;
    }
    this.recovery = null;
    this.emit();
  }

  useRecoveryText(text: string) {
    const recovery = this.recovery;
    if (recovery?.kind === 'mismatch') {
      this.recoveryActionId += 1;
      this.recoveryActionPending = false;
      this.serverRevision = recovery.serverRevision;
      this.serverText = recovery.serverText;
    }
    this.conflict = null;
    this.recovery = null;
    this.edit(text);
  }

  async refreshRecoveryServerText(): Promise<boolean> {
    if (!this.unresolvedRecovery() || this.recoveryActionPending) return false;
    const actionId = this.recoveryActionId + 1;
    this.recoveryActionId = actionId;
    this.recoveryActionPending = true;
    this.errorMessage = null;
    this.saveState = 'conflict';
    this.emit();
    try {
      const latest = await api.get<ChapterDetail>(`/chapters/${this.chapterId}`);
      if (actionId !== this.recoveryActionId || !this.unresolvedRecovery()) return false;
      if (latest.id !== this.chapterId || latest.project_id !== this.projectId) {
        throw new Error('서버 원고 응답이 현재 회차와 맞지 않습니다.');
      }
      const serverRevision = latest.revision ?? this.serverRevision;
      this.serverRevision = serverRevision;
      this.serverText = latest.content_md;
      this.recovery = { ...this.recovery!, serverText: latest.content_md, serverRevision };
      this.errorMessage = null;
      this.saveState = 'conflict';
      this.emitAck(latest);
      return true;
    } catch (error) {
      if (actionId === this.recoveryActionId && this.unresolvedRecovery()) {
        this.errorMessage = apiMessage(error);
        this.saveState = 'conflict';
      }
      return false;
    } finally {
      if (actionId === this.recoveryActionId) {
        this.recoveryActionPending = false;
        this.emit();
      }
    }
  }

  clearConflictKeepingLocal() {
    this.conflict = null;
    this.saveState = this.text === this.serverText ? 'saved' : 'dirty';
    this.persistDraft();
    this.emit();
    this.scheduleSave();
  }

  beginServerReplacement(): ManuscriptReplacementToken {
    return {
      projectId: this.projectId,
      chapterId: this.chapterId,
      editSequence: this.editSequence,
      text: this.text,
      serverRevision: this.serverRevision,
    };
  }

  completeServerReplacement(detail: ChapterDetail, token: ManuscriptReplacementToken) {
    if (token.projectId !== this.projectId || token.chapterId !== this.chapterId) return 'ignored' as const;
    if (detail.id !== this.chapterId || detail.project_id !== this.projectId) {
      this.saveState = 'error';
      this.errorMessage = '회차가 현재 작품에 속하지 않아 교체 결과를 반영하지 않았습니다.';
      this.persistDraft();
      this.emit();
      return 'ignored' as const;
    }

    const localChangedAfterRequest = this.editSequence !== token.editSequence || this.text !== token.text;
    this.serverRevision = detail.revision ?? this.serverRevision;
    this.serverText = detail.content_md;
    this.emitAck(detail);

    if (!localChangedAfterRequest) {
      this.initialized = true;
      this.text = detail.content_md;
      this.savedSequence = this.editSequence;
      this.saveState = 'saved';
      this.errorMessage = null;
      this.conflict = null;
      this.recovery = null;
      this.removeStoredDraft();
      this.emit();
      return 'applied' as const;
    }

    if (this.timer !== undefined && typeof window !== 'undefined') {
      window.clearTimeout(this.timer);
      this.timer = undefined;
    }
    const message = '서버 교체 작업 중 새 입력이 있어 자동 덮어쓰기를 멈췄습니다. 로컬 원고를 보존했습니다.';
    this.conflict = {
      message,
      currentRevision: detail.revision ?? null,
      localText: this.text,
      serverText: detail.content_md,
      serverRevision: detail.revision ?? null,
    };
    this.saveState = 'conflict';
    this.errorMessage = message;
    this.recovery = null;
    this.persistDraft();
    this.emit();
    return 'late_edit' as const;
  }

  applyServerReplacement(detail: ChapterDetail) {
    this.completeServerReplacement(detail, this.beginServerReplacement());
  }

  async flush(): Promise<WriteResult> {
    if (this.timer !== undefined && typeof window !== 'undefined') {
      window.clearTimeout(this.timer);
      this.timer = undefined;
    }
    if (this.unresolvedRecovery()) {
      this.saveState = 'conflict';
      this.errorMessage = this.unresolvedRecoveryMessage();
      this.emit();
      throw new Error(this.errorMessage);
    }
    this.isFlushing = true;
    this.emit();
    try {
      while (true) {
        if (this.conflict) throw new Error(this.conflict.message);
        if (this.inFlight) {
          await this.inFlight;
          if (this.text === this.serverText || this.conflict) break;
          continue;
        }
        if (this.text === this.serverText) {
          this.saveState = 'saved';
          this.errorMessage = null;
          this.removeStoredDraft();
          this.emit();
          return { detail: this.asDetail() };
        }
        await this.writeCurrent();
        if (this.text === this.serverText) return { detail: this.asDetail() };
      }
      return { detail: this.asDetail() };
    } finally {
      this.isFlushing = false;
      this.emit();
    }
  }

  pagehideFlush() {
    if (this.unresolvedRecovery() || this.conflict || this.inFlight || this.text === this.serverText) return;
    try {
      void fetch(`/api/v1/chapters/${this.chapterId}/content`, {
        method: 'PUT',
        keepalive: true,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content_md: this.text, expected_revision: this.serverRevision }),
      }).catch(() => {});
    } catch { /* best effort */ }
  }

  hasUnsaved() {
    return this.text !== this.serverText || this.saveState === 'saving' || this.saveState === 'dirty' || this.saveState === 'error' || this.saveState === 'conflict';
  }

  private async writeCurrent(): Promise<WriteResult> {
    const sentText = this.text;
    const sentSeq = this.editSequence;
    const expectedRevision = this.serverRevision;
    this.inFlightSeq = sentSeq;
    this.inFlightText = sentText;
    this.saveState = 'saving';
    this.errorMessage = null;
    this.emit();

    const promise = (async () => {
      try {
        const detail = await api.put<ChapterDetail>(`/chapters/${this.chapterId}/content`, {
          content_md: sentText,
          expected_revision: expectedRevision,
        });
        this.acknowledge(detail, sentSeq, sentText);
        return { detail };
      } catch (error) {
        const conflict = conflictDetail(error);
        if (conflict) {
          await this.freezeConflict(conflict, sentText);
        } else if (error instanceof ApiError && error.status === 0) {
          const reconciled = await this.tryLostAck(sentSeq, sentText);
          if (reconciled) return reconciled;
          this.saveState = 'error';
          this.errorMessage = apiMessage(error);
          this.persistDraft();
          this.emit();
        } else {
          this.saveState = 'error';
          this.errorMessage = apiMessage(error);
          this.persistDraft();
          this.emit();
        }
        throw error;
      } finally {
        this.inFlight = null;
        this.inFlightSeq = null;
        this.inFlightText = null;
        if (!this.conflict && this.text !== this.serverText && this.saveState !== 'error') {
          this.saveState = 'dirty';
          this.emit();
        }
      }
    })();
    this.inFlight = promise;
    return promise;
  }

  private acknowledge(detail: ChapterDetail, sentSeq: number, sentText: string) {
    if (detail.id !== this.chapterId || detail.project_id !== this.projectId) {
      this.saveState = 'error';
      this.errorMessage = '회차가 현재 작품에 속하지 않아 저장 결과를 반영하지 않았습니다.';
      this.persistDraft();
      this.emit();
      return;
    }
    this.serverRevision = detail.revision ?? this.serverRevision;
    this.serverText = detail.content_md;
    this.savedSequence = Math.max(this.savedSequence, sentSeq);
    this.conflict = null;
    this.errorMessage = null;
    this.emitAck(detail);
    if (this.editSequence === sentSeq && this.text === sentText) {
      this.text = detail.content_md;
      this.saveState = 'saved';
      this.removeStoredDraft();
    } else {
      this.saveState = 'dirty';
      this.persistDraft();
      this.scheduleSaveSoon();
    }
    this.emit();
  }

  private async freezeConflict(detail: RevisionConflictDetail, localText: string) {
    const currentRevision = typeof detail.current_revision === 'number' ? detail.current_revision : null;
    let serverText: string | null = null;
    let serverRevision: number | null = currentRevision;
    try {
      const latest = await api.get<ChapterDetail>(`/chapters/${this.chapterId}`);
      if (latest.id === this.chapterId && latest.project_id === this.projectId) {
        serverText = latest.content_md;
        serverRevision = latest.revision ?? serverRevision;
        this.serverText = latest.content_md;
        this.serverRevision = latest.revision ?? this.serverRevision;
      }
    } catch { /* conflict UI can still show local text */ }
    const message = detail.message ?? '서버에 더 최신 원고가 있습니다. 로컬 원고를 보존했습니다.';
    this.conflict = { message, currentRevision, localText, serverText, serverRevision };
    this.saveState = 'conflict';
    this.errorMessage = message;
    this.persistDraft();
    this.emit();
  }

  private async tryLostAck(sentSeq: number, sentText: string): Promise<WriteResult | null> {
    try {
      const latest = await api.get<ChapterDetail>(`/chapters/${this.chapterId}`);
      if (latest.id === this.chapterId && latest.project_id === this.projectId && latest.content_md === sentText) {
        this.acknowledge(latest, sentSeq, sentText);
        return { detail: latest };
      }
    } catch { /* keep original network error */ }
    return null;
  }

  private scheduleSaveSoon() {
    if (typeof window === 'undefined') return;
    window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => void this.flush(), 0);
  }

  private persistDraft() {
    if (!isBrowser()) return;
    try {
      const draft: RecoveryDraft = {
        version: 1,
        projectId: this.projectId,
        chapterId: this.chapterId,
        baseRevision: this.serverRevision,
        editSequence: this.editSequence,
        text: this.text,
        updatedAt: Date.now(),
      };
      window.localStorage.setItem(storageKey(this.projectId, this.chapterId), JSON.stringify(draft));
      this.storageError = null;
    } catch {
      this.storageError = '복구본 저장에 실패했습니다. 편집과 서버 저장은 계속할 수 있습니다.';
    }
  }

  private removeStoredDraft() {
    if (!isBrowser()) return;
    try {
      window.localStorage.removeItem(storageKey(this.projectId, this.chapterId));
      this.storageError = null;
    } catch {
      this.storageError = '복구본 정리에 실패했습니다.';
    }
  }

  private loadRecovery(detail: ChapterDetail) {
    if (!isBrowser()) return;
    try {
      const raw = window.localStorage.getItem(storageKey(this.projectId, this.chapterId));
      if (!raw) return;
      const parsed = JSON.parse(raw) as Partial<RecoveryDraft>;
      if (parsed.version !== 1 || parsed.projectId !== this.projectId || parsed.chapterId !== this.chapterId || typeof parsed.text !== 'string' || typeof parsed.baseRevision !== 'number') return;
      const serverRevision = detail.revision ?? 0;
      if (parsed.text === detail.content_md) {
        this.removeStoredDraft();
        return;
      }
      if (parsed.baseRevision === serverRevision) {
        this.text = parsed.text;
        this.editSequence = Math.max(this.editSequence + 1, parsed.editSequence ?? 1);
        this.saveState = 'dirty';
        this.recovery = { kind: 'restored', message: '로컬 복구본을 불러왔습니다. 자동 저장으로 서버에 다시 반영합니다.', localText: parsed.text, serverText: detail.content_md, baseRevision: parsed.baseRevision, serverRevision };
        this.persistDraft();
        this.scheduleSave();
      } else {
        this.recovery = { kind: 'mismatch', message: '로컬 복구본과 서버 원고가 다릅니다. 자동으로 덮어쓰지 않습니다.', localText: parsed.text, serverText: detail.content_md, baseRevision: parsed.baseRevision, serverRevision };
        this.saveState = 'conflict';
      }
    } catch {
      this.storageError = '복구본을 읽을 수 없습니다. 서버 원고로 계속합니다.';
    }
  }

  private asDetail(): ChapterDetail {
    return {
      id: this.chapterId,
      project_id: this.projectId,
      volume: null,
      sort_order: 0,
      title: '',
      status: '초고',
      word_count_cache: this.serverText.replace(/\s/g, '').length,
      memo: null,
      revision: this.serverRevision,
      content_md: this.serverText,
      created_at: '',
      updated_at: '',
    };
  }
}

const coordinators = new Map<string, ManuscriptDraftCoordinator>();

export function getManuscriptDraft(projectId: number, chapterId: number) {
  const key = keyFor(projectId, chapterId);
  let coordinator = coordinators.get(key);
  if (!coordinator) {
    coordinator = new ManuscriptDraftCoordinator(projectId, chapterId);
    coordinators.set(key, coordinator);
  }
  return coordinator;
}

export function useManuscriptDraft({
  projectId,
  chapterId,
  serverDetail,
  onServerDetail,
}: {
  projectId: number;
  chapterId: number;
  serverDetail?: ChapterDetail;
  onServerDetail?: (detail: ChapterDetail) => void;
}) {
  const coordinator = useMemo(() => getManuscriptDraft(projectId, chapterId), [projectId, chapterId]);
  const snapshot = useSyncExternalStore(coordinator.subscribe, coordinator.getSnapshot, coordinator.getSnapshot);

  useEffect(() => {
    if (serverDetail) coordinator.initFromServer(serverDetail);
  }, [coordinator, serverDetail]);

  useEffect(() => {
    if (!onServerDetail) return undefined;
    return coordinator.onAck(onServerDetail);
  }, [coordinator, onServerDetail]);

  useEffect(() => {
    const onPageHide = () => coordinator.pagehideFlush();
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!coordinator.hasUnsaved()) return;
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('pagehide', onPageHide);
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => {
      window.removeEventListener('pagehide', onPageHide);
      window.removeEventListener('beforeunload', onBeforeUnload);
    };
  }, [coordinator]);

  return {
    ...snapshot,
    edit: (text: string) => coordinator.edit(text),
    flush: () => coordinator.flush(),
    clearRecovery: () => coordinator.clearRecovery(),
    useRecoveryText: (text: string) => coordinator.useRecoveryText(text),
    refreshRecoveryServerText: () => coordinator.refreshRecoveryServerText(),
    clearConflictKeepingLocal: () => coordinator.clearConflictKeepingLocal(),
    beginServerReplacement: () => coordinator.beginServerReplacement(),
    completeServerReplacement: (detail: ChapterDetail, token: ManuscriptReplacementToken) =>
      coordinator.completeServerReplacement(detail, token),
    applyServerReplacement: (detail: ChapterDetail) => coordinator.applyServerReplacement(detail),
  };
}

export async function flushManuscriptDraft(projectId: number, chapterId: number) {
  return getManuscriptDraft(projectId, chapterId).flush();
}

export function beginManuscriptReplacement(projectId: number, chapterId: number) {
  return getManuscriptDraft(projectId, chapterId).beginServerReplacement();
}

export function completeManuscriptReplacement(
  projectId: number,
  chapterId: number,
  detail: ChapterDetail,
  token: ManuscriptReplacementToken,
) {
  return getManuscriptDraft(projectId, chapterId).completeServerReplacement(detail, token);
}

export function applyManuscriptServerDetail(projectId: number, chapterId: number, detail: ChapterDetail) {
  getManuscriptDraft(projectId, chapterId).applyServerReplacement(detail);
}

export function getManuscriptDraftState(projectId: number, chapterId: number) {
  return getManuscriptDraft(projectId, chapterId).getSnapshot();
}
