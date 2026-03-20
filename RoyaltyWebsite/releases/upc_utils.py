"""
UPC normalization for Sonosuite compatibility.
Sonosuite expects 13-digit EAN-13 (with leading 0 when needed).
Our system: store and use 13 digits; if user enters 12 digits, pad with leading 0.
"""
import re


def normalize_upc_to_13(upc: str) -> str:
    """
    Normalize UPC to exactly 13 digits for storage and Sonosuite API.
    - Strip non-digits.
    - If 12 digits: prepend one '0' to make 13 digits (EAN-13).
    - If 13 digits: return as-is.
    - If empty or invalid: return empty string.
    """
    if not upc:
        return ""
    digits = re.sub(r"\D", "", str(upc))
    if len(digits) == 12:
        return "0" + digits
    if len(digits) == 13:
        return digits
    if len(digits) > 13:
        return digits[:13]
    # 11 or fewer: return as-is (don't pad to 13 with leading zeros except for 12->13)
    return digits


def find_release_by_upc(upc: str, model_class):
    """
    Look up a Release by UPC, accepting both 12-digit (821460144772) and
    13-digit (0821460144772) forms. Sonosuite uses 13-digit; our DB may have 12.
    Returns the Release instance or None.
    """
    if not (upc or "").strip():
        return None
    upc = str(upc).strip()
    digits = re.sub(r"\D", "", upc)
    if not digits:
        return None
    # Try as stored (might be 12 or 13 digits)
    try:
        return model_class.objects.get(upc=upc)
    except model_class.DoesNotExist:
        pass
    normalized_13 = normalize_upc_to_13(upc)
    if normalized_13 and normalized_13 != upc:
        try:
            return model_class.objects.get(upc=normalized_13)
        except model_class.DoesNotExist:
            pass
    # If input was 13 digits with leading 0, try 12-digit form (strip leading 0)
    if len(digits) == 13 and digits.startswith("0"):
        try:
            return model_class.objects.get(upc=digits[1:])
        except model_class.DoesNotExist:
            pass
    return None
