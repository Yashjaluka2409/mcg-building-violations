from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Same envelope as the MCG platform: {count, next, previous, results} with ?page_size=."""
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 500
