"""Estados e erros localizados compartilhados pela integração com o YouTube."""
from __future__ import annotations


class IntegrationError(Exception):
    def __init__(self, message: str, status: str = "error"):
        super().__init__(message)
        self.status = status


class CredentialsNotConfigured(IntegrationError):
    def __init__(self):
        super().__init__("Importe o arquivo OAuth do Google Cloud para conectar o YouTube.", "disconnected")


class InvalidClientSecrets(IntegrationError):
    def __init__(self):
        super().__init__("O arquivo OAuth é inválido. Use um cliente OAuth do tipo Aplicativo para computador.",
                         "error")


class CredentialStoreUnavailable(IntegrationError):
    def __init__(self):
        super().__init__("O Gerenciador de Credenciais do Windows está indisponível. Verifique o keyring do sistema.",
                         "unavailable")


class AuthenticationRequired(IntegrationError):
    def __init__(self):
        super().__init__("A conta do YouTube está desconectada. Conecte-a novamente em Integrações.", "disconnected")


class AuthenticationExpired(IntegrationError):
    def __init__(self):
        super().__init__("A autorização do Google expirou ou foi revogada. Reconecte sua conta do YouTube.", "expired")


class PermissionRequired(IntegrationError):
    def __init__(self):
        super().__init__("A conta não autorizou as permissões necessárias para consultar e enviar vídeos.", "expired")


class LoginCancelled(IntegrationError):
    def __init__(self):
        super().__init__("A autenticação foi cancelada ou não foi concluída no navegador.", "disconnected")


class ChannelNotFound(IntegrationError):
    def __init__(self):
        super().__init__("Nenhum canal do YouTube foi encontrado para esta conta Google.", "error")


class DuplicatePublication(IntegrationError):
    def __init__(self):
        super().__init__("Este arquivo já foi enviado ou está com o resultado do envio pendente para este canal.",
                         "duplicate")


class UploadCancelled(IntegrationError):
    def __init__(self):
        super().__init__("O envio foi cancelado antes de ser concluído.", "cancelled")


class UploadOutcomeUnknown(IntegrationError):
    def __init__(self):
        super().__init__("Não foi possível confirmar o resultado do envio. Verifique o YouTube Studio antes de tentar novamente.",
                         "unknown")


def friendly_api_error(exc: Exception) -> IntegrationError:
    """Converte erros HTTP do Google em mensagens seguras e úteis para a interface."""
    response = getattr(exc, "resp", None)
    code = getattr(response, "status", None)
    try:
        content = getattr(exc, "content", b"")
        detail = content.decode("utf-8", "replace") if isinstance(content, bytes) else str(content)
    except Exception:  # resposta malformada; não propagar detalhes potencialmente sensíveis
        detail = ""
    lower = detail.lower()
    if code == 401 or "invalid_grant" in lower:
        return AuthenticationExpired()
    if code == 403:
        if any(x in lower for x in ("quotaexceeded", "dailylimitexceeded", "uploadlimitexceeded")):
            return IntegrationError("A cota ou o limite de uploads do YouTube foi atingido. Tente novamente mais tarde.",
                                    "error")
        if "youtube signup required" in lower or "channel not found" in lower:
            return ChannelNotFound()
        if any(x in lower for x in ("insufficientpermissions", "insufficient authentication scopes", "forbidden")):
            return PermissionRequired()
        if "youtube data api has not been used" in lower or "accessnotconfigured" in lower or "service_disabled" in lower:
            return IntegrationError("A YouTube Data API v3 não está habilitada no projeto Google Cloud das credenciais.",
                                    "unavailable")
        return IntegrationError("O Google recusou a operação. Confira as permissões da conta e do canal.", "error")
    if code == 429:
        return IntegrationError("O YouTube recebeu muitas solicitações seguidas. Aguarde um pouco antes de tentar novamente.",
                                "error")
    if code == 400:
        return IntegrationError("O YouTube recusou os metadados. Confira o título, a descrição e as opções escolhidas.",
                                "error")
    if code in (408, 429, 500, 502, 503, 504) or code is None:
        return IntegrationError("Não foi possível concluir a comunicação com o YouTube. Verifique a conexão e o histórico.",
                                "error")
    return IntegrationError("O YouTube não concluiu a operação. Consulte o histórico de publicações.", "error")
