"""Canonical narrative order shared by lists, neighbors and future references."""
from math import inf

from sqlalchemy import and_, or_

from app.models import Chapter


def chapter_position(chapter: Chapter) -> tuple[float, float, int]:
    return (chapter.volume if chapter.volume is not None else inf, chapter.sort_order, chapter.id)


def chapter_ordering(*, reverse: bool = False):
    if reverse:
        return (Chapter.volume.desc().nulls_first(), Chapter.sort_order.desc(), Chapter.id.desc())
    return (Chapter.volume.asc().nulls_last(), Chapter.sort_order.asc(), Chapter.id.asc())


def neighbor_condition(chapter: Chapter, *, previous: bool):
    same_volume = Chapter.volume.is_(None) if chapter.volume is None else Chapter.volume == chapter.volume
    same_volume_position = or_(
        Chapter.sort_order < chapter.sort_order if previous else Chapter.sort_order > chapter.sort_order,
        and_(Chapter.sort_order == chapter.sort_order,
             Chapter.id < chapter.id if previous else Chapter.id > chapter.id),
    )
    within_volume = and_(same_volume, same_volume_position)
    if chapter.volume is None:
        return or_(Chapter.volume.is_not(None), within_volume) if previous else within_volume
    other_volume = Chapter.volume < chapter.volume if previous else or_(
        Chapter.volume > chapter.volume, Chapter.volume.is_(None),
    )
    return or_(other_volume, within_volume)
