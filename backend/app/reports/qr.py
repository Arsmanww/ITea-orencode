from io import BytesIO

import qrcode
from qrcode.constants import ERROR_CORRECT_M


def qr_png(data: str, box_size: int = 8) -> bytes:
    """QR-код в PNG. Уровень коррекции M – читается и с распечатанной справки."""
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=box_size, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    buffer = BytesIO()
    qr.make_image(fill_color="#0A3C96", back_color="white").save(buffer, format="PNG")
    return buffer.getvalue()
