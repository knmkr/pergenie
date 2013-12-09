# -*- coding: utf-8 -*-

import sys, os
import glob
import shutil
from pprint import pprint
from optparse import make_option

from pymongo import MongoClient
# from termcolor import colored
from django.core.management.base import BaseCommand
from django.conf import settings
from lib.api.genomes import Genomes
genomes = Genomes()
from lib.api.riskreport import RiskReport
riskreport = RiskReport()
from lib.utils import clogging
log = clogging.getColorLogger(__name__)


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option(
            "--variants",
            action='store_true',
            help=""
        ),
        make_option(
            "--riskreports",
            action='store_true',
            help=""
        ),
        make_option(
            "--user",
            action='store_true',
            help=""
        ),
    )

    def handle(self, *args, **options):
        if not args:
            self.print_help("show", "help")
            return

        log.info('Drop collections...')

        with MongoClient(host=settings.MONGO_URI) as c:
            db = c['pergenie']
            data_info = db['data_info']

            if options["variants"]:
                # Show collection `variants.file_uuid`
                for user_id in args:
                    pprint([x.name for x in genomes.get_all_variants(user_id)])

                # Show document in `data_info`
                # targets = []
                # for user_id in args:
                #     targets += list(data_info.find({'user_id': user_id}))

            if options["riskreports"]:
                for user_id in args:
                    pprint([x.name for x in riskreport.get_all_riskreports(user_id)])

            if options["user"]:
                print 'sorry, not implemented yet...'
                return
                # # rm `dir`
                # targets = []
                # for user_id in args:
                #     targets += glob.glob(os.path.join(settings.UPLOAD_DIR, user_id))  # FIXME: use UUID ?

                # pprint(targets)
                # print '...will be deleted'
                # yn = raw_input('y/n > ')