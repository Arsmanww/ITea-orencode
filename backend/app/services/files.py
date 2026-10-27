from urllib.parse import quote

from fastapi import Response


def attachment(content: bytes, media_type: str, ascii_name: str, display_name: str) -> Response:
    """Ответ-вложение; русское имя файла передаётся по RFC 5987 (filename*)."""
    disposition = f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(display_name)}'
    return Response(content=content, media_type=media_type, headers={"Content-Disposition": disposition})
