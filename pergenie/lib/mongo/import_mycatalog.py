import sys, os
import csv
from pymongo import MongoClient
from django.conf import settings

from utils import clogging
log = clogging.getColorLogger(__name__)


def import_mycatalog(path_to_mycatalog):
    with MongoClient(host=settings.MONGO_URI) as c:
        db = c['pergenie']
        mycatalog = db['mycatalog']

        if mycatalog.find_one():
            db.drop_collection(mycatalog)

        with open(path_to_mycatalog, 'r') as fin:
            for record in csv.DictReader(fin, delimiter=','):
                record = dict((key.replace(' ', '_'), value) for (key, value) in record.items())
                mycatalog.insert(record)
