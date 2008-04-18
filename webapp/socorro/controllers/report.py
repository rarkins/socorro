from socorro.lib.base import *
from socorro.lib.processor import Processor
from socorro.models import Report, Job, PriorityJob
from socorro.lib.queryparams import BySignatureLimit, getReportsForParams
from socorro.lib.http_cache import responseForKey
import socorro.lib.collect as collect
import socorro.lib.config as config
from sqlalchemy import *
from sqlalchemy.databases.postgres import *
import re
from pylons.database import create_engine
from cStringIO import StringIO

matchDumpID = re.compile('^(%s)?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$' % config.dumpIDPrefix)

class ReportController(BaseController):
  def index(self, id):
    c.report = Report.by_id(id)

    # If we get no id, 404 -- id can't be blank.
    if id is None:
      abort(404, 'Page Not Found')

    # If we don't have a report entry, see if it's in the queue.
    # If it's there, flag it for priority so the user can see it in ~10 seconds.
    #
    # This should not be cached, so we explicitly send no-cache response
    # headers.
    if c.report is None:

      # The pending page adds ?p=1 to redirects.  Check this to avoid inserting 
      # duplicate priorityjob entries.  
      try:
        request.params['p']
      except(KeyError):
        c.priority = PriorityJob.add(id)

      h.redirect_to(action='pending', id=id)

    # If we have the report entry, show it as usual.
    else:
      if c.report['build']:
        resp = responseForKey(c.report['uuid'], expires=(60 * 60))
      else:
        resp = responseForKey(c.report['uuid'])

      resp.write(render('report/index'))
      return resp

  def pending(self, id):

    # If we get no id, 404 -- id can't be blank.
    if id is None:
      abort(404, 'Page Not Found')

    # Check to see if the report already got processed at some point and redirect to it if so.
    c.report = Report.by_id(id)
    if c.report is not None:
      h.redirect_to(action='index', id=id)

    c.job = Job.by_uuid(id)

    return render_response('report/pending')

  def find(self):
    # This method should not touch the database!
    uuid = None
    if 'id' in request.params:
      match = matchDumpID.search(request.params['id'])
      if match is not None:
        uuid = match.group(2)

    if uuid is not None:
      h.redirect_to(action='index', id=uuid)
    else:
      h.redirect_to('/')

  def list(self):
    c.params = BySignatureLimit()
    c.params.setFromParams(request.params)
    key = "reportlist_%s" % request.environ["QUERY_STRING"]
    (c.reports, c.builds, ts) = getReportsForParams(c.params, key)
    resp = responseForKey("%s%s" % (ts,key))
    resp.write(render('report/list'))
    return resp

  def add(self):
    #
    # Turn this off for now, until it can be tested again
    #
    if False:
      #
      # xx fix this
      symbol_dir = g.pylons_config.app_conf['socorro.symbol_dir']
      minidump = g.pylons_config.app_conf['socorro.minidump_stackwalk']

      crash_dump = request.POST['upload_file_minidump']
      if not crash_dump.file:
        #XXXsayrer set a 4xx status
        return Response('Bad request')

      # mirror the process used by the standalone collectors
      (dumpID, dumpPath) = collect.storeDump(crash_dump.file)
      collect.storeJSON(dumpID, dumpPath, request.POST)
      processor = Processor(minidump, [symbol_dir])
      processor.process(dumpPath, dumpID)
      return Response(collect.makeResponseForClient(dumpID))

    else:
      h.log('bad request?')
      #XXXsayrer set a 4xx status
      return Response('Bad request')
