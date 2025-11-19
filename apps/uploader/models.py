"""Models for uploader app.

BlobMeta - metadata about stored blobs (id is the primary key and is a string)
BlobData - optional table used when the DB storage backend is selected to store actual binary data
"""
from tortoise import fields, models


class BlobMeta(models.Model):
    # id can be any string (uuid, path, random) and serves as the unique reference
    id = fields.CharField(pk=True, max_length=255)
    size = fields.IntField()
    backend = fields.CharField(max_length=50, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        default_connection = "default"
        table = "blobs_meta"


class BlobData(models.Model):
    """Stores binary data when using the database storage backend.

    The id mirrors BlobMeta.id and is the primary key here as well.
   """
    id = fields.CharField(pk=True, max_length=255)
    data = fields.BinaryField()

    class Meta:
        default_connection = "default"
        table = "blobs_data"
