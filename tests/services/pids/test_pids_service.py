# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 CERN
#
# Invenio-RDM-Records is free software; you can redistribute it
# and/or modify it under the terms of the MIT License; see LICENSE file for
# more details.

"""PID related tests for Invenio RDM Records.

This tests both the PIDsService and the RDMService behaviour related to pids.
"""

from collections import namedtuple

import pytest
from invenio_pidstore.errors import PIDDoesNotExistError
from invenio_pidstore.models import PIDStatus
from marshmallow import ValidationError

from invenio_rdm_records.proxies import current_rdm_records

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


#
# Reserve & Discard
#

def test_resolve_pid(running_app, es_clear, minimal_record):
    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    # create the draft
    draft = service.create(superuser_identity, minimal_record)
    # publish the record
    record = service.publish(draft.id, superuser_identity)
    doi = record["pids"]["doi"]["identifier"]

    # test resolution
    resolved_record = service.pids.resolve(
        id_=doi,
        identity=superuser_identity,
        pid_type="doi"
    )
    assert resolved_record.id == record.id
    assert resolved_record["pids"]["doi"]["identifier"] == doi


def test_resolve_non_existing_pid(running_app, es_clear, minimal_record):
    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    # create the draft
    draft = service.create(superuser_identity, minimal_record)
    # publish the record
    service.publish(draft.id, superuser_identity)

    # test resolution
    fake_doi = "10.1234/client.12345-abdce"
    with pytest.raises(PIDDoesNotExistError):
        service.pids.resolve(
            id_=fake_doi,
            identity=superuser_identity,
            pid_type="doi"
        )


def test_reserve_pid(running_app, es_clear, minimal_record):
    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    # create the draft
    draft = service.create(superuser_identity, minimal_record)
    draft = service.pids.create(draft.id, superuser_identity, "doi")
    # publish the record
    doi = draft["pids"]["doi"]["identifier"]
    provider = service.pids.get_provider("doi", "datacite")
    pid = provider.get(pid_value=doi)
    assert pid.status == PIDStatus.NEW


def test_discard_exisisting_pid(running_app, es_clear, minimal_record):
    # note discard is only performed over NEW pids for pids in status RESERVED
    # or REGISTERED the invalidate function must be used
    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    # create the draft
    draft = service.create(superuser_identity, minimal_record)
    draft = service.pids.create(draft.id, superuser_identity, "doi")
    # publish the record
    doi = draft["pids"]["doi"]["identifier"]
    provider = service.pids.get_provider("doi", "datacite")
    pid = provider.get(pid_value=doi)
    assert pid.status == PIDStatus.NEW
    draft = service.pids.discard(draft.id, superuser_identity, "doi")
    assert not draft["pids"].get("doi")
    with pytest.raises(PIDDoesNotExistError):
        pid = provider.get(pid_value=doi)


def test_discard_non_exisisting_pid(running_app, es_clear, minimal_record):
    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    # create the draft
    draft = service.create(superuser_identity, minimal_record)
    with pytest.raises(ValidationError):
        service.pids.discard(draft.id, superuser_identity, "doi")


#
# Workflows
#
#  Use cases list:
#
# | Creation
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Draft creation from scratch (no pid)             | basic_flow                            |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Publish with no pid (creation of mandatory ones) | basic_flow                            |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Do not allow duplicates                          | duplicates                            |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Fail on empty (invalid) value for external pid   | creation_invalid_external_payload     |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
#
# | Reservation
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Reserve pid                                      | reserve_managed                       |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Fail to reserve with already existing managed    | reserve_fail_existing_managed         |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Fail to reserve with already existing external   | reserve_fail_existing_external        |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
#
# | Update on drafts (prefix test_pids_drafts)
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Update from external to managed on a draft       | updates_external_to_managed           |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Update from external to no pid on a draft        | updates_external_to_managed           |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Update from managed to external on a draft       | updates_managed_to_external           |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Update from managed to no pid on a draft         | updates_managed_to_no_pid             |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Update from no pid to external on a draft        | updates_no_pid_to_external            |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Update from no pid to managed on a draft         | updates_no_pid_to_managed             |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
#
# | Update on records
# | Note that cases with no function assigned are not testable because doi is mandatory and     # noqa
# | one will always be assinged on publishing.
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Update from external to managed on a record      | updates_flow_external_to_managed      |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Update from external to no pid on a record       | updates_flow_external_to_managed      |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Update from managed to external on a record      | updates_flow_managed_to_external      |  # noqa
# |                                                  | updates_managed_to_external_perm_fail |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Update from managed to no pid on a record        | updates_flow_managed_to_no_pid        |  # noqa
# |                                                  | updates_managed_to_no_pid_perm_fail   |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Update from no pid to external on a record       |                                       |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Update from no pid to managed on a record        |                                       |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
#
# | Publishing
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Publish with a managed pid (from reserve)        | publish_managed                       |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Publish with an external pid                     | publish_external                      |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
#
# | Deletion
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Delete a draft with a managed pid                | delete_managed_pid_from_draft         |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Delete a draft with an external pid              | delete_external_pid_from_draft        |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Delete an edit (draft) with a managed pid        | delete_managed_pid_from_record        |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa
# | Delete an edit (draft) with an external pid      | delete_external_pid_from_record       |  # noqa
# |--------------------------------------------------|---------------------------------------|  # noqa


# Creation

def test_pids_basic_flow(running_app, es_clear, minimal_record):
    # external doi and mandatory assignation when empty pids
    # is tested at resources level
    superuser_identity = running_app.superuser_identity
    service = current_rdm_records.records_service
    minimal_record["pids"] = {}

    # create the draft
    draft = service.create(superuser_identity, minimal_record)
    assert draft["pids"] == {}

    # publish the record with a managed PID
    record = service.publish(draft.id, superuser_identity)
    published_doi = record["pids"]["doi"]
    assert published_doi["identifier"]
    assert published_doi["provider"] == "datacite"  # default
    provider = service.pids.get_provider("doi", "datacite")
    pid = provider.get(pid_value=published_doi["identifier"])
    assert pid.status == PIDStatus.REGISTERED  # registration is async


def test_pids_duplicates(running_app, es_clear, minimal_record):
    superuser_identity = running_app.superuser_identity
    service = current_rdm_records.records_service
    provider = service.pids.get_provider("doi", "datacite")
    # create an external pid for an already existing NEW managed one
    draft = service.create(superuser_identity, minimal_record)
    draft = service.pids.create(draft.id, superuser_identity, "doi")
    doi = draft["pids"]["doi"]["identifier"]

    data = minimal_record.copy()
    data["pids"]["doi"] = {
        "identifier": doi,
        "provider": "external"
    }

    duplicated_draft = service.create(superuser_identity, data)
    error_msg = {
        'field': 'pids.doi',
        'message': [f'doi:{doi} already exists.']
    }
    assert error_msg in duplicated_draft.errors

    # create an external pid for an already existing RESERVED managed one
    record = service.publish(draft.id, superuser_identity)

    duplicated_draft = service.create(superuser_identity, data)
    error_msg = {
        'field': 'pids.doi',
        'message': [f'doi:{doi} already exists.']
    }
    assert error_msg in duplicated_draft.errors

    # create an external pid for an already existing external one
    data = minimal_record.copy()
    doi = "10.1234/test.1234"
    data["pids"]["doi"] = {"identifier": doi, "provider": "external"}
    draft = service.create(superuser_identity, data)
    record = service.publish(draft.id, superuser_identity)

    duplicated_draft = service.create(superuser_identity, data)
    error_msg = {
        'field': 'pids.doi',
        'message': [f'doi:{doi} already exists.']
    }
    assert error_msg in duplicated_draft.errors

    # create a managed pid for an already existing external one
    draft = service.create(superuser_identity, minimal_record)
    doi = draft["pids"]["doi"]["identifier"]
    data = minimal_record.copy()
    data["pids"]["doi"] = {"identifier": doi, "provider": "external"}

    duplicated_draft = service.create(superuser_identity, data)
    error_msg = {
        'field': 'pids.doi',
        'message': [f'doi:{doi} already exists.']
    }
    assert error_msg in duplicated_draft.errors


def test_pids_creation_invalid_external_payload(
    running_app, es_clear, minimal_record
):
    superuser_identity = running_app.superuser_identity
    service = current_rdm_records.records_service

    data = minimal_record.copy()
    data["pids"]["doi"] = {
        "identifier": "",
        "provider": "external",
    }

    draft = service.create(superuser_identity, data)
    assert draft.errors == [
        {'field': 'pids', 'messages': ['Invalid value for scheme doi']}
    ]


# Reservation

def test_pids_reserve_managed(running_app, es_clear, minimal_record):
    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    provider = service.pids.get_provider("doi", "datacite")

    # create the draft
    draft = service.create(superuser_identity, minimal_record)
    # "reserve" pid
    draft = service.pids.create(draft.id, superuser_identity, "doi")
    doi = draft["pids"]["doi"]["identifier"]
    pid = provider.get(pid_value=doi)
    assert pid.status == PIDStatus.NEW


def test_pids_reserve_fail_existing_managed(
    running_app, es_clear, minimal_record
):
    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    provider = service.pids.get_provider("doi", "datacite")

    # create the draft
    draft = service.create(superuser_identity, minimal_record)
    # "reserve" pid (first assignation)
    draft = service.pids.create(draft.id, superuser_identity, "doi")
    doi = draft["pids"]["doi"]["identifier"]
    pid = provider.get(pid_value=doi)
    assert pid.status == PIDStatus.NEW
    # reserve again
    with pytest.raises(ValidationError):
        service.pids.create(draft.id, superuser_identity, "doi")


def test_pids_reserve_fail_existing_external(
    running_app, es_clear, minimal_record
):
    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    provider = service.pids.get_provider("doi", "datacite")

    # create the draft
    data = minimal_record.copy()
    data["pids"]["doi"] = {
        "identifier": "10.1234/dummy.1234",
        "provider": "external"
    }
    draft = service.create(superuser_identity, minimal_record)
    # reserve again
    with pytest.raises(ValidationError):
        service.pids.create(draft.id, superuser_identity, "doi")


# Update on drafts

def test_pids_drafts_updates_external_to_managed(
    running_app, es_clear, minimal_record
):
    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    provider = service.pids.get_provider("doi", "datacite")

    # create the draft
    data = minimal_record.copy()
    data["pids"]["doi"] = {
        "identifier": "10.1234/dummy.1234",
        "provider": "external"
    }
    draft = service.create(superuser_identity, minimal_record)
    with pytest.raises(PIDDoesNotExistError):  # pid should not exist
        provider.get(
            pid_value=draft["pids"]["doi"]["identifier"],
            pid_provider="external"
        )

    # remove and reserve a managed one
    # managed pids needs to first be created (reserve)
    draft["pids"].pop("doi")
    draft = service.update_draft(
        id_=draft.id, identity=superuser_identity, data=draft.data)
    assert not draft["pids"].get("doi")

    draft = service.pids.create(draft.id, superuser_identity, "doi")
    doi = draft["pids"]["doi"]["identifier"]
    assert provider.get(pid_value=doi).status == PIDStatus.NEW


def test_pids_drafts_updates_managed_to_external(
    running_app, es_clear, minimal_record
):
    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    provider = service.pids.get_provider("doi", "datacite")

    # create the draft
    draft = service.create(superuser_identity, minimal_record)
    draft = service.pids.create(draft.id, superuser_identity, "doi")
    doi = draft["pids"]["doi"]["identifier"]
    assert provider.get(pid_value=doi).status == PIDStatus.NEW

    # replace by external
    draft["pids"]["doi"] = {
        "identifier": "10.1234/dummy.1234",
        "provider": "external"
    }
    draft = service.update_draft(
        id_=draft.id, identity=superuser_identity, data=draft.data)

    assert draft["pids"]["doi"]["identifier"] == "10.1234/dummy.1234"
    assert draft["pids"]["doi"]["provider"] == "external"

    with pytest.raises(PIDDoesNotExistError):  # pid should not exist
        provider.get(
            pid_value=draft["pids"]["doi"]["identifier"],
            pid_provider="external"
        )

    with pytest.raises(PIDDoesNotExistError):  # original doi was also deleted
        provider.get(pid_value=doi)


def test_pids_drafts_updates_managed_to_no_pid(
    running_app, es_clear, minimal_record
):
    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    provider = service.pids.get_provider("doi", "datacite")

    # create the draft
    draft = service.create(superuser_identity, minimal_record)
    draft = service.pids.create(draft.id, superuser_identity, "doi")
    doi = draft["pids"]["doi"]["identifier"]
    assert provider.get(pid_value=doi).status == PIDStatus.NEW

    # remove doi
    draft["pids"].pop("doi")
    draft = service.update_draft(
        id_=draft.id, identity=superuser_identity, data=draft.data)

    assert not draft["pids"].get("doi")
    with pytest.raises(PIDDoesNotExistError):  # original doi was also deleted
        provider.get(pid_value=doi)


def test_pids_drafts_updates_no_pid_to_external(
    running_app, es_clear, minimal_record
):
    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    provider = service.pids.get_provider("doi", "datacite")

    # create the draft
    draft = service.create(superuser_identity, minimal_record)
    assert draft["pids"] == {}

    # add external
    draft["pids"]["doi"] = {
        "identifier": "10.1234/dummy.1234",
        "provider": "external"
    }
    draft = service.update_draft(
        id_=draft.id, identity=superuser_identity, data=draft.data)

    assert draft["pids"]["doi"]["identifier"] == "10.1234/dummy.1234"
    assert draft["pids"]["doi"]["provider"] == "external"

    with pytest.raises(PIDDoesNotExistError):  # pid should not exist
        provider.get(
            pid_value=draft["pids"]["doi"]["identifier"],
            pid_provider="external"
        )


def test_pids_drafts_updates_no_pid_to_managed(
    running_app, es_clear, minimal_record
):
    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    provider = service.pids.get_provider("doi", "datacite")

    # create the draft
    draft = service.create(superuser_identity, minimal_record)
    assert draft["pids"] == {}

    # add managed
    draft = service.pids.create(draft.id, superuser_identity, "doi")
    doi = draft["pids"]["doi"]["identifier"]
    assert provider.get(pid_value=doi).status == PIDStatus.NEW


# Update on records

def _create_and_publish_external(service, provider, identity, data):
    """Creates a draft with a managed doi and publishes it."""
    # create the draft
    data["pids"]["doi"] = {
        "identifier": "10.1234/dummy.1234",
        "provider": "external"
    }
    draft = service.create(identity, data)
    # publish and check the doi is in pidstore
    record = service.publish(draft.id, identity)
    pid = provider.get(pid_value="10.1234/dummy.1234")
    assert pid.status == PIDStatus.REGISTERED

    return record


def _create_and_publish_managed(service, provider, identity, data):
    """Creates a draft with a managed doi and publishes it."""
    # create the draft
    draft = service.create(identity, data)
    # "reserve" pid if not given
    draft = service.pids.create(draft.id, identity, "doi")
    doi = draft["pids"]["doi"]["identifier"]
    pid = provider.get(pid_value=doi)
    assert pid.status == PIDStatus.NEW
    # publish and check the doi is in pidstore
    record = service.publish(draft.id, identity)
    assert provider.get(pid_value=doi).status == PIDStatus.REGISTERED

    return record


def test_pids_records_updates_external_to_managed(
    running_app, es_clear, minimal_record, identity_simple
):
    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    provider = service.pids.get_provider("doi", "datacite")
    record = _create_and_publish_external(
        service, provider, superuser_identity, minimal_record)

    # create draft
    draft = service.edit(record.id, superuser_identity)
    # remove external pid allowed
    doi = draft["pids"].pop("doi")
    draft = service.update_draft(
        id_=draft.id, identity=superuser_identity, data=draft.data)
    assert not draft["pids"].get("doi")
    pid = provider.get(
        pid_value=doi["identifier"], pid_provider=doi["provider"]
    )
    assert pid.status == PIDStatus.DELETED
    # add a new managed doi
    draft = service.pids.create(draft.id, superuser_identity, "doi")
    doi = draft["pids"]["doi"]["identifier"]
    pid = provider.get(pid_value=doi)
    assert pid.status == PIDStatus.NEW


def test_pids_records_updates_managed_to_external(
    running_app, es_clear, minimal_record, identity_simple, mocker
):

    def hide_doi(self, doi):
        """Mock doi hide."""
        pass

    mocker.patch("invenio_rdm_records.services.pids.providers.datacite." +
                 "DataCiteRESTClient.hide_doi", hide_doi)

    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    provider = service.pids.get_provider("doi", "datacite")
    record = _create_and_publish_managed(
        service, provider, superuser_identity, minimal_record)

    # create draft
    draft = service.edit(record.id, superuser_identity)
    # replace by external doi
    ext_pid = {
        "identifier": "10.1234/dummy.1234",
        "provider": "external"
    }
    draft["pids"]["doi"] = ext_pid
    draft = service.update_draft(
        id_=draft.id, identity=superuser_identity, data=draft.data)
    assert draft["pids"]["doi"] == ext_pid
    # previous managed doi deleted
    pid = provider.get(pid_value=record["pids"]["doi"]["identifier"])
    assert pid.status == PIDStatus.DELETED


def test_pids_records_updates_managed_to_external_perm_fail(
    running_app, es_clear, minimal_record, authenticated_identity
):
    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    provider = service.pids.get_provider("doi", "datacite")
    record = _create_and_publish_managed(
        service, provider, authenticated_identity, minimal_record)

    # create draft
    draft = service.edit(record.id, authenticated_identity)
    # replace by external doi
    ext_pid = {
        "identifier": "10.1234/dummy.1234",
        "provider": "external"
    }
    draft["pids"]["doi"] = ext_pid
    draft = service.update_draft(
        id_=draft.id, identity=authenticated_identity, data=draft.data)
    # authenticated user is owner but is not superuser/admin
    pids_error = {
        'field': 'pids.doi',
        'message': 'Permission denied: cannot update PID.'
    }
    assert pids_error in draft.errors
    doi = draft["pids"]["doi"]["identifier"]
    assert doi
    assert provider.get(pid_value=doi).status == PIDStatus.REGISTERED


def test_pids_records_updates_managed_to_no_pid(
    running_app, es_clear, minimal_record, identity_simple, mocker
):
    def hide_doi(self, doi):
        """Mock doi hide."""
        pass

    mocker.patch("invenio_rdm_records.services.pids.providers.datacite." +
                 "DataCiteRESTClient.hide_doi", hide_doi)

    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    provider = service.pids.get_provider("doi", "datacite")
    record = _create_and_publish_managed(
        service, provider, superuser_identity, minimal_record)

    # create draft
    draft = service.edit(record.id, superuser_identity)
    # remove doi
    draft["pids"].pop("doi")
    draft = service.update_draft(
        id_=draft.id, identity=superuser_identity, data=draft.data)
    assert not draft["pids"].get("doi")
    # previous managed doi deleted
    pid = provider.get(pid_value=record["pids"]["doi"]["identifier"])
    assert pid.status == PIDStatus.DELETED


def test_pids_records_updates_managed_to_no_pid_perm_fail(
    running_app, es_clear, minimal_record, authenticated_identity
):
    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    provider = service.pids.get_provider("doi", "datacite")
    record = _create_and_publish_managed(
        service, provider, authenticated_identity, minimal_record)

    # create draft
    draft = service.edit(record.id, authenticated_identity)
    # fail to remove doi due to lack of permissions
    draft["pids"].pop("doi")
    draft = service.update_draft(
        id_=draft.id, identity=authenticated_identity, data=draft.data)
    # authenticated user is owner but is not superuser/admin
    pids_error = {
        'field': 'pids.doi',
        'message': 'Permission denied: cannot update PID.'
    }
    assert pids_error in draft.errors
    doi = draft["pids"]["doi"]["identifier"]
    assert doi
    assert provider.get(pid_value=doi).status == PIDStatus.REGISTERED


# Publishing

def test_pids_publish_managed(running_app, es_clear, minimal_record):
    superuser_identity = running_app.superuser_identity
    service = current_rdm_records.records_service
    provider = service.pids.get_provider("doi", "datacite")

    # create the draft
    draft = service.create(superuser_identity, minimal_record)
    draft = service.pids.create(draft.id, superuser_identity, "doi")
    doi = draft["pids"]["doi"]["identifier"]
    assert provider.get(pid_value=doi).status == PIDStatus.NEW

    # publish
    record = service.publish(draft.id, superuser_identity)
    # registration is async
    assert provider.get(pid_value=doi).status == PIDStatus.REGISTERED


def test_pids_publish_external(running_app, es_clear, minimal_record):
    superuser_identity = running_app.superuser_identity
    service = current_rdm_records.records_service
    provider = service.pids.get_provider("doi", "datacite")

    # create the draft
    data = minimal_record.copy()
    data["pids"]["doi"] = {
        "identifier": "10.1234/dummy.1234",
        "provider": "external"
    }
    draft = service.create(superuser_identity, data)
    with pytest.raises(PIDDoesNotExistError):  # pid should not exist
        provider.get(
            pid_value=draft["pids"]["doi"]["identifier"],
            pid_provider="external"
        )

    # publish
    record = service.publish(draft.id, superuser_identity)
    pid = provider.get(
        pid_value=record["pids"]["doi"]["identifier"],
        pid_provider="external"
    )
    assert pid.pid_value == record["pids"]["doi"]["identifier"]
    # registration is async
    assert pid.status == PIDStatus.REGISTERED


# Deletion

def test_pids_delete_external_pid_from_draft(
    running_app, es_clear, minimal_record
):
    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    provider = service.pids.get_provider("doi", "datacite")

    # create draft
    data = minimal_record.copy()
    data["pids"] = {
        "doi": {"identifier": "10.1234/dummy.1234", "provider": "external"}
    }
    draft = service.create(superuser_identity, data)

    # delete draft
    assert service.delete_draft(draft.id, superuser_identity)
    with pytest.raises(PIDDoesNotExistError):  # pid should not exist
        provider.get(
            pid_value=data["pids"]["doi"]["identifier"],
            pid_provider="external"
        )


def test_pids_delete_managed_pid_from_draft(
    running_app, es_clear, minimal_record
):
    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    provider = service.pids.get_provider("doi", "datacite")

    # create draft and doi
    draft = service.create(superuser_identity, minimal_record)
    draft = service.pids.create(draft.id, superuser_identity, "doi")
    pid = provider.get(pid_value=draft["pids"]["doi"]["identifier"])
    assert pid.status == PIDStatus.NEW
    assert pid.pid_value == draft["pids"]["doi"]["identifier"]

    # delete draft
    assert service.delete_draft(draft.id, superuser_identity)
    with pytest.raises(PIDDoesNotExistError):  # pid should not exist
        provider.get(pid_value=pid.pid_value, pid_provider="external")


def test_pids_delete_external_pid_from_record(
    running_app, es_clear, minimal_record
):
    # This test aims to delete from a draft created out of a published record
    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    provider = service.pids.get_provider("doi", "datacite")

    # create draft
    data = minimal_record.copy()
    data["pids"] = {
        "doi": {"identifier": "10.1234/dummy.1234", "provider": "external"}
    }
    draft = service.create(superuser_identity, data)
    # publish
    record = service.publish(draft.id, superuser_identity)
    pid = provider.get(
        pid_value=record["pids"]["doi"]["identifier"],
        pid_provider=record["pids"]["doi"]["provider"]
    )
    assert pid.status == PIDStatus.REGISTERED
    assert pid.pid_value == record["pids"]["doi"]["identifier"]
    # create new draft
    draft = service.edit(record.id, superuser_identity)
    pid = provider.get(
        pid_value=draft["pids"]["doi"]["identifier"],
        pid_provider=draft["pids"]["doi"]["provider"]
    )
    assert pid.status == PIDStatus.REGISTERED
    assert pid.pid_value == draft["pids"]["doi"]["identifier"]
    # delete draft (should not delete pid since it is part of an active record)
    assert service.delete_draft(draft.id, superuser_identity)
    pid = provider.get(
        pid_value=record["pids"]["doi"]["identifier"],
        pid_provider=record["pids"]["doi"]["provider"]
    )
    assert pid.status == PIDStatus.REGISTERED
    assert pid.pid_value == record["pids"]["doi"]["identifier"]


def test_pids_delete_managed_pid_from_record(
    running_app, es_clear, minimal_record
):
    # This test aims to delete from a draft created out of a published record
    service = current_rdm_records.records_service
    superuser_identity = running_app.superuser_identity
    provider = service.pids.get_provider("doi", "datacite")

    # create draft and managed doi
    draft = service.create(superuser_identity, minimal_record)
    draft = service.pids.create(draft.id, superuser_identity, "doi")
    # publish
    record = service.publish(draft.id, superuser_identity)
    pid = provider.get(pid_value=record["pids"]["doi"]["identifier"])
    assert pid.status == PIDStatus.REGISTERED
    assert pid.pid_value == record["pids"]["doi"]["identifier"]
    # create new draft
    draft = service.edit(record.id, superuser_identity)
    pid = provider.get(pid_value=draft["pids"]["doi"]["identifier"])
    assert pid.status == PIDStatus.REGISTERED
    assert pid.pid_value == draft["pids"]["doi"]["identifier"]
    # delete draft (should not delete pid since it is part of an active record)
    assert service.delete_draft(draft.id, superuser_identity)
    pid = provider.get(pid_value=record["pids"]["doi"]["identifier"])
    assert pid.status == PIDStatus.REGISTERED
    assert pid.pid_value == record["pids"]["doi"]["identifier"]


#
# Versioning
#

def test_pids_versioning():
    # TODO: implement
    # versioning flow
    # create draft and publish
    # concept doi + doi
    # new version + publish
    # concept doi still the same, doi is different
    pass