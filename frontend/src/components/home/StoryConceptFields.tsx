import type { StoryConcept } from "@/lib/api";
import { Label } from "@/components/ui/label";

export type StoryConceptKey = keyof StoryConcept;

const CONCEPT_FIELDS: ReadonlyArray<{
  key: StoryConceptKey;
  label: string;
  placeholder: string;
  maxLength: number;
}> = [
  {
    key: "summary",
    label: "한 문장 전제",
    placeholder: "예: 기억을 잃은 세무사가 죽은 이들의 빚을 갚아야 집으로 돌아간다.",
    maxLength: 1000,
  },
  {
    key: "protagonist",
    label: "주인공",
    placeholder: "결핍·능력·출발점을 적어보세요.",
    maxLength: 500,
  },
  {
    key: "inciting_incident",
    label: "촉발 사건",
    placeholder: "이야기를 시작시키고 주인공을 움직이는 사건은 무엇인가요?",
    maxLength: 500,
  },
  {
    key: "goal",
    label: "목표",
    placeholder: "주인공이 이루려는 구체적인 목표는 무엇인가요?",
    maxLength: 500,
  },
  {
    key: "opposition",
    label: "대립",
    placeholder: "목표를 막는 인물·세력·조건은 무엇인가요?",
    maxLength: 500,
  },
  {
    key: "stakes",
    label: "위험·대가",
    placeholder: "실패하면 무엇을 잃거나 어떤 대가를 치르나요?",
    maxLength: 500,
  },
  {
    key: "hook",
    label: "차별화 후크",
    placeholder: "이 작품만의 설정·규칙·서사 장치는 무엇인가요?",
    maxLength: 500,
  },
];

export function compactStoryConcept(value: StoryConcept): StoryConcept | null {
  const compact: StoryConcept = {};
  for (const { key } of CONCEPT_FIELDS) {
    const text = value[key];
    if (typeof text === "string" && text.trim()) {
      compact[key] = text.trim();
    }
  }
  return Object.keys(compact).length > 0 ? compact : null;
}

export function storyConceptSummary(
  value: StoryConcept | null | undefined,
): string | null {
  const compact = value ? compactStoryConcept(value) : null;
  if (!compact) return null;
  for (const { key } of CONCEPT_FIELDS) {
    const text = compact[key];
    if (typeof text === "string") return text;
  }
  return null;
}

export function StoryConceptFields({
  value,
  onChange,
  idPrefix,
  showOptionalDetails = true,
}: {
  value: StoryConcept;
  onChange: (value: StoryConcept) => void;
  idPrefix: string;
  showOptionalDetails?: boolean;
}) {
  const summary = CONCEPT_FIELDS[0];
  const details = CONCEPT_FIELDS.slice(1);

  const renderField = ({
    key,
    label,
    placeholder,
    maxLength,
  }: (typeof CONCEPT_FIELDS)[number]) => {
    const id = `${idPrefix}-${key}`;
    return (
      <div key={key} className="flex flex-col gap-1.5">
        <Label htmlFor={id}>{label}</Label>
        <textarea
          id={id}
          className="min-h-16 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          placeholder={placeholder}
          value={value[key] ?? ""}
          maxLength={maxLength}
          rows={key === "summary" ? 2 : 3}
          onChange={(event) =>
            onChange({ ...value, [key]: event.target.value })
          }
        />
      </div>
    );
  };

  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="text-sm font-semibold">작품 컨셉 (선택)</legend>
      <p className="text-xs text-muted-foreground">
        장르나 분위기 이름이 아니라, 주인공이 어떤 사건에서 무엇을 걸고 움직이는지
        적습니다. AI 부트스트랩에서 비워두면 AI가 서사 전제를 제안하고, 수동 저장에서는 컨셉 없이 저장됩니다.
      </p>
      {renderField(summary)}
      {showOptionalDetails && (
        <details className="rounded-md border border-border px-3 py-2">
          <summary className="cursor-pointer text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            컨셉 구성요소 더 입력하기
          </summary>
          <div className="mt-3 flex flex-col gap-3">
            {details.map(renderField)}
          </div>
        </details>
      )}
    </fieldset>
  );
}
