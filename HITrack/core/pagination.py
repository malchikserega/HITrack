from rest_framework.pagination import PageNumberPagination

class CustomPageNumberPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 1000


class ClusterImagePagination(PageNumberPagination):
    """Keep cluster detail responses bounded even for very large clusters."""

    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200
