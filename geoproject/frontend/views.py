from django.shortcuts import render
from django.http import JsonResponse
from django.core.files.storage import FileSystemStorage
from rest_framework.parsers import JSONParser
from .models import data
from .serializers import dataSerializer
# Create your views here.


def index(request):
    if request.method == 'POST':
        uploaded_file = request.FILES['document']
        fs = FileSystemStorage(location="../media/Excelfiles/")
        fs.save(uploaded_file.name, uploaded_file)

    return render(request, 'frontend/index.html')


def data_list(request):
    if request.method == 'GET':
        values = data.objects.all()
        serializer = dataSerializer(values, many=True)
        return JsonResponse(serializer.data, safe=False)
