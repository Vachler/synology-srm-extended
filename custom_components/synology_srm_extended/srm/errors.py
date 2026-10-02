"""Výjimky neobsahují těla odpovědí, adresy ani přihlašovací údaje."""


class SrmError(Exception):
    """Základ bezpečných chyb klienta."""


class TransportError(SrmError):
    """Router není dostupný nebo nevrací platnou HTTP odpověď."""


class CertificateError(TransportError):
    """Nepodařilo se ověřit TLS certifikát."""


class ResponseError(SrmError):
    """Neočekávaná struktura odpovědi."""


class ApiError(SrmError):
    """Číselná chyba SRM, bez textu dodaného serverem."""

    def __init__(self, code: int) -> None:
        self.code = code
        super().__init__(f"SRM API: {code}")


class AuthenticationError(ApiError):
    """Přihlášení nebo obnova relace selhala."""


class TwoFactorRequired(AuthenticationError):
    """Přihlašovací tok vyžaduje další faktor; zatím není podporován."""


class UnsupportedError(ApiError):
    """API nebo konkrétní verze/metoda nejsou dostupné."""


class PermissionDenied(ApiError):
    """Účet nemá oprávnění; nejde o expirovanou relaci."""
