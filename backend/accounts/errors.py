from django.http import JsonResponse
from rest_framework.views import exception_handler

def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        original = response.data
        response.data = {'code': getattr(exc, 'default_code', 'error'), 'message': 'Request could not be completed.', 'fields': original}
    return response

def csrf_failure(request, reason=''):
    return JsonResponse({'code': 'csrf_failed', 'message': 'Security token missing or invalid.'}, status=403)
