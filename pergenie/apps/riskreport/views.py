import sys, os
import datetime
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.generic.simple import direct_to_template
from django.shortcuts import redirect, render
from django.http import HttpResponse, Http404
from django.utils.translation import get_language
from django.utils.translation import ugettext as _
from django.conf import settings
from models import *
from apps.riskreport.forms import RiskReportForm

from lib.api.user import User
user = User()
from lib.api.genomes import Genomes
genomes = Genomes()
from utils import clogging
log = clogging.getColorLogger(__name__)

# mimetype = {'csv': 'application/comma-separated-values',
#             'tsv': 'application/tab-separated-values',
#             'zip': 'application/zip'}

@require_http_methods(['GET', 'POST'])
@login_required
def index(request):
    """
    Summary view for risk report.
    * Show top-10 highest & top-10 lowest risk values.
    * Link to `show all`
    """
    user_id = request.user.username
    msg, err = '', ''
    browser_language = get_language()
    do_intro = False
    tmp_info = None
    h_risk_traits, h_risk_values, h_risk_ranks, h_risk_studies = None, None, None, None
    file_name = ''
    force_uptade = False

    while True:
        infos = genomes.get_data_infos(user_id)

        if not infos:
            err = _('no data uploaded')
            break

        # Determine file_name & tmp_info
        tmp_user_info = user.get_user_info(user_id)

        if not tmp_user_info:
            # user does not exists in user_info...
            err = _('invalid user')
            break

        if not request.method == 'POST':
            while True:
                # By default, browse `last_viewed_file` if exists.
                if tmp_user_info.get('last_viewed_file'):
                    if genomes.get_data_info(user_id, tmp_user_info['last_viewed_file']):
                        if genomes.get_data_info(user_id, tmp_user_info['last_viewed_file'])['status'] == 100:
                            tmp_info = genomes.get_data_info(user_id, tmp_user_info['last_viewed_file'])
                            file_name = tmp_info['name']
                            break

                # If this is the first time, choose first file_name in infos (with status == 100).
                for info in infos:
                    if info['status'] == 100:
                        file_name = info['name']
                        tmp_info = info
                        break

                if not tmp_info:
                    err = _('Your files are in importing, please wait for seconds...')
                    break

                break

        # If file_name is selected by user with Form,
        elif request.method == 'POST':
            form = RiskReportForm(request.POST)

            if not form.is_valid():
                err = _('Invalid request.')
                break

            file_name = request.POST.get('file_name')
            population = request.POST.get('population')

            print request.POST

            for info in infos:
                if info['name'] == file_name:
                    if info['status'] == 100:
                        tmp_info = info

                        break
                    else:
                        err = _('%(file_name)s is in importing, please wait for seconds...') % {'file_name': file_name}

            if err:
                break

            if not tmp_info:
                err = _('no such file %(file_name)s') % {'file_name': file_name}
                break

            if population in ['unknown', 'Asian', 'European', 'Japanese']:
                # Change population
                if tmp_info['population'] != population:
                    force_uptade = True
                    user.set_user_data_population(user_id, file_name, population)
                    tmp_info['population'] = population

        # Selected file_name exists & has been imported, so calculate risk.
        if not err:
            # get top-10 highest & top-10 lowest
            h_risk_traits, h_risk_values, h_risk_ranks, h_risk_studies = get_risk_values_for_indexpage(tmp_info, category=['Disease'], is_higher=True, top=10, force_uptade=force_uptade)

            # set `last_viewed_file`
            user.set_user_last_viewed_file(user_id, file_name)

            # reload
            tmp_info = genomes.get_data_info(user_id, file_name)

            # translate to Japanese
            if browser_language == 'ja':
                h_risk_traits = [TRAITS2JA.get(trait) for trait in h_risk_traits]

            # If this is the first time for riskreport,
            if ([bool(info.get('riskreport')) for info in infos].count(True) == 0):
                do_intro = True

            # For demo
            if not tmp_user_info.get('last_viewed_file'):
                do_intro = True

        break

    return direct_to_template(request, 'risk_report/index.html',
                              dict(msg=msg, err=err, infos=infos, tmp_info=tmp_info, do_intro=do_intro, file_name=file_name,
                                   h_risk_traits=h_risk_traits, h_risk_values=h_risk_values,
                                   h_risk_ranks=h_risk_ranks, h_risk_studies=h_risk_studies
                                   ))


@require_http_methods(['GET'])
@login_required
def study(request, trait, study):
    user_id = request.user.username
    msg, err = '', ''
    risk_infos = None

    while True:
        trait = JA2TRAITS.get(trait, trait)
        trait_eng = trait

        if not trait in TRAITS:
            err = _('trait not found')
            raise Http404

        # # no need ?
        # if not request.method == 'GET':
        #     return redirect('apps.riskreport.views.index')

        # Determine `file_name`.
        # If file_name is selected,
        file_name = request.GET.get('file_name')

        if not file_name:
            # By default, browse `last_viewed_file`
            file_name = user.get_user_info(user_id).get('last_viewed_file')

            # If you have no riskreports, but this time you try to browse details of reprort,
            if not file_name:
                return redirect('apps.riskreport.views.index')

        info = genomes.get_data_info(user_id, file_name)

        if not info:
            err = _('no such file %(file_name)s') % {'file_name': file_name}
            raise Http404

        # Trait & file_name exists, so get the risk information about this trait.
        risk_infos = get_risk_infos_for_subpage(info, trait=trait, study=study)
        risk_infos.update(dict(msg=msg, file_name=file_name, info=info, trait_eng=trait_eng,
                               wiki_url_en=TRAITS2WIKI_URL_EN.get(trait),
                               is_ja=bool(get_language() == 'ja')))
        break

    return direct_to_template(request, 'risk_report/study.html', risk_infos)


@login_required
def trait(request, trait):
    """Show risk value by studies, for each trait.
    """

    # user_id = request.user.username
    # trait = JA2TRAITS.get(trait, trait)
    # risk_infos = get_risk_infos_for_subpage(user_id, file_name, trait)

    # risk_infos.update(dict(msg=msg, err=err, file_name=file_name,
    #                        wiki_url_en=TRAITS2WIKI_URL_EN.get(trait),
    #                        is_ja=bool(get_language() == 'ja')))

    # return direct_to_template(request, 'risk_report/trait.html', risk_infos)
    return redirect('apps.riskreport.views.index')

@login_required
def export(request):
    """Download riskreport
    """
    user_id = request.user.username
    file_name = request.GET.get('file_name')

    if file_name:
        file_info = genomes.get_data_info(user_id, file_name)
        file_infos = [file_info] if file_info else []
    else:
        file_infos = genomes.get_data_infos(user_id)
    if not file_infos:
        raise Http404

    fout_path = riskreport.write_riskreport(user_id, file_infos)
    if not fout_path:
        raise Http404

    fout = open(fout_path, 'rb').read()
    response = HttpResponse(fout, mimetype='application/zip')
    response['Content-Disposition'] = 'filename=' + os.path.basename(fout_path)
    return response

@require_http_methods(['GET', 'POST'])
@login_required
def show_all(request):
    """
    Show all risk values in a chart.
    * It can compare two individual genomes.

    TODO:
    * Do not use log-scale. Replace to real-scale.
    * Enable to click & link trait-name in charts. (currently bar in charts only)
    * Show population in charts, e.g., `Japanese national flag`, etc.
    """

    user_id = request.user.username
    msg, err = '', ''
    # risk_reports, risk_traits, risk_values = None, None, None
    risk_traits, risk_values, risk_ranks, risk_studies = [], [], [], []
    do_intro = False
    browser_language = get_language()

    while True:
        # determine file
        infos = genomes.get_data_infos(user_id)
        tmp_info = None
        tmp_infos = []

        if not infos:
            err = _('no data uploaded')
            break

        if not request.method == 'POST':
            tmp_user_info = user.get_user_info(user_id)
            file_name = tmp_user_info.get('last_viewed_file')

            # If you have no riskreports, but this time you try to browse details of reprort,
            if not file_name:
                return redirect('apps.riskreport.views.index')

            tmp_infos.append(genomes.get_data_info(user_id, file_name))

            # Intro.js
            if not tmp_user_info.get('viewed_riskreport_showall'):
                log.debug(tmp_user_info.get('viewed_riskreport_showall'))
                user.set_user_viewed_riskreport_showall_done(user_id)
                do_intro = True

        # If file_name is selected by user with Form,
        elif request.method == 'POST':
            form = RiskReportForm(request.POST)
            if not form.is_valid():
                err = _('Invalid request.')
                break

            #
            for i, file_name in enumerate([request.POST['file_name'], request.POST['file_name2']]):
                for info in infos:
                    if info['name'] == file_name:
                        if not info['status'] == 100:
                            err = _('%(file_name)s is in importing, please wait for seconds...') % {'file_name': file_name}

                        tmp_info = info
                        tmp_infos.append(tmp_info)
                        break

                if not tmp_info:
                    err = _('no such file %(file_name)s') % {'file_name': file_name}
                    break

        if not err:
            for i,tmp_info in enumerate(tmp_infos):
                tmp_risk_traits, tmp_risk_values, tmp_risk_ranks, tmp_risk_studies = get_risk_values_for_indexpage(tmp_infos[i], category=['Disease'])

                # Data for person A
                if i == 0:
                    risk_traits = tmp_risk_traits
                    risk_values.append(tmp_risk_values)
                    risk_ranks.append(tmp_risk_ranks)
                    risk_studies.append(tmp_risk_studies)

                # Data for person B. (Traits in chart is based on person A, so some traits are not in person B.)
                if i == 1:
                    risk_values.append([])
                    risk_ranks.append([])
                    risk_studies.append([])

                    for trait in risk_traits:
                        if not trait in tmp_risk_traits:
                            risk_values[1].append(0.0)
                            risk_ranks[1].append('na')
                            risk_studies[1].append('na')

                        else:
                            j = tmp_risk_traits.index(trait)
                            risk_values[1].append(tmp_risk_values[j])
                            risk_ranks[1].append(tmp_risk_ranks[j])
                            risk_studies[1].append(tmp_risk_studies[j])

            # Translate to Japanese
            if browser_language == 'ja':
                risk_traits = [TRAITS2JA.get(trait) for trait in risk_traits]

        break

    return direct_to_template(request, 'risk_report/show_all.html',
                              dict(msg=msg, err=err, infos=infos, tmp_infos=tmp_infos, do_intro=do_intro,
                                   risk_traits=risk_traits, risk_values=risk_values, risk_ranks=risk_ranks, risk_studies=risk_studies))

@require_http_methods(['GET', 'POST'])
@login_required
def show_all_files(request):
    """
    """

    user_id = request.user.username
    msg, err = '', ''
    # risks = list()

    # infos = genomes.get_data_infos(user_id)
    # for i,info in enumerate(infos):
    #     # Get riskreports
    #     tmp_risk_traits, tmp_risk_values, tmp_risk_ranks, tmp_risk_studies = get_risk_values_for_indexpage(infos[i], category=['Disease'])

    #     # Count by RR
    #     # {***: {count: ***, trait: "***,***,***"}, ...
    #     result = dict()
    #     for trait, value in zip(tmp_risk_traits, tmp_risk_values):
    #         if not value in result:
    #             result[value] = {'count': 1, 'trait': trait}
    #         else:
    #             result[value]['count'] += 1
    #             result[value]['trait'] += "," + trait

    #     risks.append([info['raw_name'], result])

    # # Sort by filename
    # risks = sorted(risks, key=lambda x:x[0])

    # return direct_to_template(request, 'risk_report/show_all_files.html',
    #                           dict(msg=msg, err=err, infos=infos, risks=risks))
    return direct_to_template(request, 'risk_report/show_all_files.html',
                              {})
