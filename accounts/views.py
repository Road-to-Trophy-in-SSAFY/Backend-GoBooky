from django.shortcuts import render
from rest_framework import generics
from rest_framework.permissions import AllowAny
from .models import Category
from .serializers import CategorySerializer


# Create your views here.
class CategoryListView(generics.ListAPIView):
    """
    카테고리 목록을 반환하는 API 뷰
    회원가입 시 필요한 카테고리 목록 조회에 사용됨
    """

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]  # 모든 사용자가 접근 가능하도록 설정
