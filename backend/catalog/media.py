"""Private, bounded image library. Bytes and metadata commit atomically."""
from hashlib import sha256
from io import BytesIO
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from django.db import transaction
from django.http import HttpResponse
from rest_framework import generics, permissions, serializers
from rest_framework.generics import get_object_or_404
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.serializers import StrictSerializer
from accounts.services import audit
from .models import MediaAsset

LIMIT = 5 * 1024 * 1024
PIXELS = 12_000_000
KINDS = ('poster', 'cover', 'logo', 'photo')

class MediaPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        action = 'view' if request.method in permissions.SAFE_METHODS else ('add' if request.method == 'POST' else 'change')
        return request.user.is_authenticated and request.user.has_perm('catalog.'+action+'_mediaasset')

class Upload(StrictSerializer):
    name = serializers.CharField(max_length=150)
    kind = serializers.ChoiceField(choices=KINDS)
    alt_text = serializers.CharField(max_length=250, allow_blank=True, required=False)
    file = serializers.FileField()

class Change(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=150, required=False)
    kind = serializers.ChoiceField(choices=KINDS, required=False)
    alt_text = serializers.CharField(max_length=250, allow_blank=True, required=False)
    is_active = serializers.BooleanField(required=False)
    def validate(self, attrs):
        if len(attrs) == 1:
            raise serializers.ValidationError('No changes supplied.')
        return attrs

class Output(serializers.ModelSerializer):
    class Meta:
        model = MediaAsset
        fields = ('id','name','kind','alt_text','mime_type','width','height','size_bytes','sha256','is_active','version','created_at','updated_at')


def clean_image(upload):
    if not 0 < upload.size <= LIMIT:
        raise serializers.ValidationError({'file':'Maximum file size is 5 MiB.'})
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(upload) as source:
                fmt = source.format
                if fmt not in ('JPEG','PNG') or getattr(source, 'n_frames', 1) != 1 or source.width * source.height > PIXELS:
                    raise ValueError('Unsupported format or dimensions')
                source.load()
                oriented = ImageOps.exif_transpose(source)
                mode = 'RGBA' if fmt == 'PNG' else 'RGB'
                clean = Image.new(mode, oriented.size)
                clean.paste(oriented.convert(mode))
                buf = BytesIO()
                clean.save(buf, format=fmt)
                width, height = clean.size
                content = buf.getvalue()
    except (OSError, ValueError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise serializers.ValidationError({'file':'Upload a valid single-frame JPEG or PNG of at most 12 megapixels.'})
    if len(content) > LIMIT:
        raise serializers.ValidationError({'file':'Processed image exceeds 5 MiB. Resize the image.'})
    return dict(content=content, mime_type='image/jpeg' if fmt == 'JPEG' else 'image/png', width=width, height=height, size_bytes=len(content), sha256=sha256(content).hexdigest())

class MediaList(generics.ListAPIView):
    permission_classes = [MediaPermission]
    serializer_class = Output
    parser_classes = [MultiPartParser]
    def get_queryset(self):
        qs = MediaAsset.objects.defer('content')
        state = self.request.query_params.get('status','active')
        if state not in ('active','archived','all'):
            raise serializers.ValidationError({'status':'Invalid status.'})
        if state != 'all':
            qs = qs.filter(is_active=state == 'active')
        term = self.request.query_params.get('search','').strip()[:150]
        if term:
            qs = qs.filter(name__icontains=term)
        kind = self.request.query_params.get('kind','')
        if kind:
            if kind not in KINDS:
                raise serializers.ValidationError({'kind':'Invalid media kind.'})
            qs = qs.filter(kind=kind)
        return qs
    def post(self, request):
        data = Upload(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        processed = clean_image(values.pop('file'))
        with transaction.atomic():
            row = MediaAsset.objects.create(created_by=request.user, **values, **processed)
            audit(request.user,'media_created',row.pk,sha256=row.sha256,size_bytes=row.size_bytes)
        return Response(Output(row).data,status=201)

class MediaDetail(APIView):
    permission_classes = [MediaPermission]
    parser_classes = [JSONParser]
    def get(self,request,pk):
        return Response(Output(get_object_or_404(MediaAsset.objects.defer('content'),pk=pk)).data)
    @transaction.atomic
    def patch(self,request,pk):
        data = Change(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        row = get_object_or_404(MediaAsset.objects.defer('content').select_for_update(),pk=pk)
        if values.pop('expected_version') != row.version:
            return Response({'code':'stale_version','message':'Refresh media before editing.'},status=409)
        old = row.is_active
        for key,value in values.items():
            setattr(row,key,value)
        row.version += 1
        row.save(update_fields=[*values,'version','updated_at'])
        action = 'media_updated' if old == row.is_active else ('media_restored' if row.is_active else 'media_archived')
        audit(request.user,action,row.pk,fields=sorted(values),version=row.version)
        return Response(Output(row).data)

class MediaContent(APIView):
    permission_classes = [MediaPermission]
    def get(self,request,pk):
        row = get_object_or_404(MediaAsset,pk=pk)
        if not row.is_active and not request.user.has_perm('catalog.change_mediaasset'):
            from django.http import Http404
            raise Http404
        response = HttpResponse(bytes(row.content),content_type=row.mime_type)
        extension = 'png' if row.mime_type == 'image/png' else 'jpg'
        response['Content-Disposition'] = f'inline; filename="{row.pk}.{extension}"'
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
