# Copyright (C) 2016 Cuckoo Foundation.
# This file is part of Cuckoo Sandbox - http://www.cuckoosandbox.org
# See the file 'docs/LICENSE' for copying permission.

try:
    import gevent.monkey
    gevent.monkey.patch_all()
    HAVE_GEVENT = True
except ImportError:
    HAVE_GEVENT = False

import logging
import os
import time
import sys

from cuckoo.misc import set_cwd

try:
    from cuckoo.distributed.app import create_app
    from cuckoo.distributed.db import Node
    from cuckoo.distributed.instance import scheduler, handle_node
    HAVE_FLASKSQLA = True
except ImportError:
    HAVE_FLASKSQLA = False

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("cuckoo.distributed.worker")

def with_app(fn, *args, **kwargs):
    with app.app_context():
        fn(*args, **kwargs)

def spawner():
    while True:
        for node in Node.query.filter_by(mode="normal").all():
            tn = node.name, node.enabled
            tr = node.name, not node.enabled

            if tn in workers:
                continue

            # This is a new worker.
            if tr not in workers:
                if node.enabled:
                    log.debug("Started new worker: %s", node.name)
                    workers[tn] = gevent.spawn(
                        with_app, handle_node, node.name
                    )
                else:
                    log.debug("Registered disabled worker: %s", node.name)
                    workers[tn] = None
                continue

            # This worker was toggled.
            if node.enabled:
                log.debug("Resumed worker: %s", node.name)
                workers[tn] = gevent.spawn(
                    with_app, handle_node, node.name
                )
                workers.pop(tr)
            else:
                log.debug("Paused worker: %s", node.name)
                workers.pop(tr).kill()
                workers[tn] = None

        time.sleep(5)

if os.environ.get("CUCKOO_APP") == "worker":
    set_cwd(os.environ["CUCKOO_CWD"])

    if not HAVE_GEVENT or not HAVE_FLASKSQLA:
        sys.exit(
            "Please install Distributed Cuckoo dependencies (through "
            "`pip install cuckoo[distributed]`)"
        )

    # Create the Flask object and push its context so that we can reuse the
    # database connection throughout our script.
    app = create_app()

    workers = {
        ("dist.scheduler", True): gevent.spawn(with_app, scheduler),
    }

    with_app(spawner)
