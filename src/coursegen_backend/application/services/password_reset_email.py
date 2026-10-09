"""Composes the password recovery e-mail sent to users."""

from coursegen_backend.application.ports.email import EmailMessage

PASSWORD_RESET_SUBJECT = "Redefinição de senha · CourseGen Studio"


def build_password_reset_email(
    recipient: str,
    full_name: str,
    reset_link: str,
    validity_minutes: int,
) -> EmailMessage:
    """Build the recovery message, written in Brazilian Portuguese.

    Parameters
    ----------
    recipient : str
        E-mail address of the user.
    full_name : str
        Name of the user, used in the greeting.
    reset_link : str
        Link to the page where the new password is defined.
    validity_minutes : int
        How long the link stays valid.

    Returns
    -------
    EmailMessage
        Message ready to be sent.
    """
    first_name = full_name.split()[0] if full_name.strip() else full_name
    body = (
        f"Olá, {first_name}.\n\n"
        "Recebemos um pedido para redefinir a senha da sua conta no "
        "CourseGen Studio.\n\n"
        "Para definir uma nova senha, acesse o link abaixo:\n"
        f"{reset_link}\n\n"
        f"O link vale por {validity_minutes} minutos e só pode ser usado "
        "uma vez. Ao redefinir a senha, todas as sessões abertas serão "
        "encerradas.\n\n"
        "Se você não fez esse pedido, ignore este e-mail; sua senha atual "
        "continua valendo.\n\n"
        "Equipe CourseGen Studio · SynapseAI Solutions\n"
    )
    return EmailMessage(
        recipient=recipient,
        subject=PASSWORD_RESET_SUBJECT,
        body=body,
    )
