from urllib.parse import quote

from django.shortcuts import redirect


class RequireVerifiedMiddleware:
    """Every page requires a logged-in user who passed 2FA in this session.

    New views are protected without anyone remembering a decorator. The only
    exceptions are listed here, in one place.
    """

    OPEN_PREFIXES = ("/account/login/", "/static/")
    SETUP_PREFIXES = ("/account/two_factor/setup/", "/account/two_factor/qrcode/", "/account/logout/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if path.startswith(self.OPEN_PREFIXES):
            return self.get_response(request)
        if not request.user.is_authenticated:
            return redirect(f"/account/login/?next={quote(path)}")
        if not request.user.is_verified():
            if path.startswith(self.SETUP_PREFIXES):
                return self.get_response(request)
            return redirect("/account/two_factor/setup/")
        return self.get_response(request)
