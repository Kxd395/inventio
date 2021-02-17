# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Graz University of Technology.
# Copyright (C) 2021 CERN.
#
# Invenio-Records-Permissions is free software; you can redistribute it
# and/or modify it under the terms of the MIT License; see LICENSE file for
# more details.

"""Pytest configuration.

See https://pytest-invenio.readthedocs.io/ for documentation on which test
fixtures are available.
"""

import pytest
from flask_principal import Identity
from invenio_access.permissions import any_user, authenticated_user, \
    system_process
from invenio_records_permissions.generators import AnyUser, \
    AuthenticatedUser, SystemProcess

from invenio_rdm_records.records import RDMRecord
from invenio_rdm_records.services.generators import IfRestricted


def _public_record():
    record = RDMRecord({}, access={})
    record.access.protection.set("public", "public")
    return record


def _restricted_record():
    record = RDMRecord({}, access={})
    record.access.protection.set("restricted", "restricted")
    return record


def _then_needs():
    return {authenticated_user, system_process}


def _else_needs():
    return {any_user, system_process}


#
# Tests
#
@pytest.mark.parametrize(
    "field,record_fun,expected_needs_fun", [
        ("record", _public_record, _else_needs),
        ("record", _restricted_record, _then_needs),
        ("files", _public_record, _else_needs),
        ("files", _restricted_record, _then_needs),
    ]
)
def test_ifrestricted_needs(field, record_fun, expected_needs_fun):
    """Test the IfRestricted generator."""
    generator = IfRestricted(
            field,
            then_=[AuthenticatedUser(), SystemProcess()],
            else_=[AnyUser(), SystemProcess()]
    )
    assert generator.needs(record=record_fun()) == expected_needs_fun()
    assert generator.excludes(record=record_fun()) == set()


def test_ifrestricted_query():
    """Test the query generation."""
    generator = IfRestricted(
            "record",
            then_=[AuthenticatedUser()],
            else_=[AnyUser()]
    )
    assert generator.query_filter(identity=any_user).to_dict() == {
        'bool': {
            'should': [
                {'match': {'access.record': 'restricted'}},
                {'match': {'access.record': 'public'}}
            ]
        }
    }