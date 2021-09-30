# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 CERN
#
# Invenio-RDM-Records is free software; you can redistribute it
# and/or modify it under the terms of the MIT License; see LICENSE file for
# more details.

"""PID service tasks tests."""


from collections import namedtuple

import pytest
from invenio_pidstore.models import PIDStatus

from invenio_rdm_records.proxies import current_rdm_records
from invenio_rdm_records.services.pids.tasks import register_or_update_pid

RunningApp = namedtuple("RunningApp", [
    "app", "location", "superuser_identity", "resource_type_v",
    "subject_v", "languages_v", "title_type_v"
])


@pytest.fixture
def running_app(
    app, location, superuser_identity, resource_type_v, subject_v, languages_v,
        title_type_v):
    """This fixture provides an app with the typically needed db data loaded.

    All of these fixtures are often needed together, so collecting them
    under a semantic umbrella makes sense.
    """
    return RunningApp(app, location, superuser_identity,
                      resource_type_v, subject_v, languages_v, title_type_v)


def test_register_pid(
    running_app, es_clear, minimal_record, mocker
):
    """Registers a PID."""
    def public_doi(self, metadata, url, doi):
        """Mock doi deletion."""
        pass

    mocker.patch("invenio_rdm_records.services.pids.providers.datacite." +
                 "DataCiteRESTClient.public_doi", public_doi)

    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    draft = service.create(superuser_identity, minimal_record)
    draft = service.pids.create(draft.id, superuser_identity, "doi")
    doi = draft["pids"]["doi"]["identifier"]
    provider = service.pids.get_provider("doi", "datacite")
    pid = provider.get(pid_value=doi)
    record = service.record_cls.publish(draft._record)
    record.pids = {
        pid.pid_type: {
            "identifier": pid.pid_value,
            "provider": "datacite"
        }
    }
    record.metadata = draft['metadata']
    record.register()
    record.commit()
    assert pid.status == PIDStatus.NEW
    pid.reserve()
    assert pid.status == PIDStatus.RESERVED
    register_or_update_pid(pid_type="doi", pid_value=pid.pid_value,
                           recid=record["id"], provider_name="datacite")
    assert pid.status == PIDStatus.REGISTERED


def test_update_pid(running_app, es_clear, minimal_record, mocker):
    """No pid provided, creating one by default."""
    def public_doi(self, metadata, url, doi):
        """Mock doi deletion."""
        pass

    def update(self, pid, record, url=None, **kwargs):
        """Mock doi update."""
        pass

    mocker.patch("invenio_rdm_records.services.pids.providers.datacite." +
                 "DataCiteRESTClient.public_doi", public_doi)
    mocked_update = mocker.patch(
        "invenio_rdm_records.services.pids.providers.datacite." +
        "DOIDataCitePIDProvider.update"
    )

    mocked_update.side_effect = update

    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    draft = service.create(superuser_identity, minimal_record)
    record = service.publish(draft.id, superuser_identity)
    doi = record["pids"]["doi"]["identifier"]
    provider = service.pids.get_provider("doi", "datacite")
    pid = provider.get(pid_value=doi)
    assert pid.status == PIDStatus.REGISTERED
    record_edited = service.edit(record.id, superuser_identity)
    assert mocked_update.called is False
    service.publish(record_edited.id, superuser_identity)
    assert mocked_update.called is True