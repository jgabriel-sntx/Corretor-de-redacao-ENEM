from allauth.account.adapter import DefaultAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    """O cadastro é feito só pelas views customizadas de `contas`."""

    def is_open_for_signup(self, request):
        return False
