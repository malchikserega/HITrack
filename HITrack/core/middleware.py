import time
from django.conf import settings
from django.http import HttpResponseServerError

class RequestTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.timeout = getattr(settings, 'TIMEOUT', 300)  # Default to 5 minutes

    def __call__(self, request):
        start_time = time.time()

        def timeout_handler():
            elapsed = time.time() - start_time
            if elapsed > self.timeout:
                return HttpResponseServerError(
                    f'Request timeout after {elapsed:.2f} seconds'
                )
            return None

        # Add timeout handler to request
        request.timeout_handler = timeout_handler

        response = self.get_response(request)
        return response 