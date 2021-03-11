import datetime as dt
import json
import urllib.parse

import pytest
from requests_futures.sessions import FuturesSession
import responses

from harmony.harmony import BBox, Client, Collection, Request


def expected_submit_url(collection_id):
    return (f'https://harmony.uat.earthdata.nasa.gov/{collection_id}'
            '/ogc-api-coverages/1.0.0/collections/all/coverage/rangeset')


def expected_status_url(job_id):
    return f'https://harmony.uat.earthdata.nasa.gov/jobs/{job_id}'


def expected_full_submit_url(request):
    spatial_params = []
    temporal_params = []
    if request.spatial:
        w, s, e, n = request.spatial
        spatial_params = [f'subset=lat({s}:{n})', f'subset=lon({w}:{e})']
    if request.temporal:
        start = request.temporal['start']
        stop = request.temporal['stop']
        temporal_params = [f'subset=time("{start.isoformat()}":"{stop.isoformat()}")']
    query_params = '&'.join(spatial_params + temporal_params)

    return f'{expected_submit_url(request.collection.id)}?{query_params}'


def expected_job(collection_id, job_id):
    return {
        'username': 'rfeynman',
        'status': 'running',
        'message': 'The job is being processed',
        'progress': 0,
        'createdAt': '2021-02-19T18:47:31.291Z',
        'updatedAt': '2021-02-19T18:47:31.291Z',
        'links': [
            {
                'title': 'Job Status',
                'href': 'https://harmony.uat.earthdata.nasa.gov/jobs/{job_id)',
                'rel': 'self',
                'type': 'application/json'
            }
        ],
        'request': (
            'https://harmony.uat.earthdata.nasa.gov/{collection_id}/ogc-api-coverages/1.0.0'
            '/collections/all/coverage/rangeset'
            '?subset=lat(52%3A77)'
            '&subset=lon(-165%3A-140)'
            '&subset=time(%222010-01-01T00%3A00%3A00%22%3A%222020-12-30T00%3A00%3A00%22)'
        ),
        'numInputGranules': 32,
        'jobID': f'{job_id}'
    }


@responses.activate
def test_when_multiple_submits_it_only_authenticates_once():
    collection = Collection(id='C1940468263-POCLOUD')
    request = Request(
        collection=collection,
        spatial=BBox(-107, 40, -105, 42)
    )
    job_id = '3141592653-abcd-1234'
    auth_url = 'https://harmony.uat.earthdata.nasa.gov/jobs'
    responses.add(
        responses.GET,
        auth_url,
        status=200
    )
    responses.add(
        responses.GET,
        expected_submit_url(collection.id),
        status=200,
        json=expected_job(collection.id, job_id)
    )

    client = Client()
    client.submit(request)
    client.submit(request)

    assert len(responses.calls) == 3
    assert responses.calls[0].request.url == auth_url
    assert urllib.parse.unquote(responses.calls[0].request.url) == auth_url
    assert urllib.parse.unquote(responses.calls[1].request.url) == expected_full_submit_url(request)
    assert urllib.parse.unquote(responses.calls[2].request.url) == expected_full_submit_url(request)


@responses.activate
def test_with_bounding_box():
    collection = Collection(id='C1940468263-POCLOUD')
    request = Request(
        collection=collection,
        spatial=BBox(-107, 40, -105, 42)
    )
    job_id = '21469294-d6f7-42cc-89f2-c81990a5d7f4'
    responses.add(
        responses.GET,
        expected_submit_url(collection.id),
        status=200,
        json=expected_job(collection.id, job_id)
    )

    actual_job_id = Client(should_validate_auth=False).submit(request)

    assert len(responses.calls) == 1
    assert responses.calls[0].request is not None
    assert urllib.parse.unquote(responses.calls[0].request.url) == expected_full_submit_url(request)
    assert actual_job_id == job_id


@responses.activate
def test_with_temporal_range():
    collection = Collection(id='C1234-TATOOINE')
    request = Request(
        collection=collection,
        temporal={
            'start': dt.datetime(2010, 12, 1),
            'stop': dt.datetime(2010, 12, 31)
        },
    )
    job_id = '1234abcd-deed-9876-c001-f00dbad'
    responses.add(
        responses.GET, 
        expected_submit_url(collection.id),
        status=200,
        json=expected_job(collection.id, job_id)
    )

    actual_job_id = Client(should_validate_auth=False).submit(request)

    assert len(responses.calls) == 1
    assert responses.calls[0].request is not None
    assert urllib.parse.unquote(responses.calls[0].request.url) == expected_full_submit_url(request)
    assert actual_job_id == job_id


@responses.activate
def test_with_bounding_box_and_temporal_range():
    collection = Collection(id='C333666999-EOSDIS')
    request = Request(
        collection=collection,
        spatial=BBox(-107, 40, -105, 42),
        temporal={
            'start': dt.datetime(2001, 1, 1),
            'stop': dt.datetime(2003, 3, 31)
        },
    )
    job_id = '1234abcd-1234-9876-6666-999999abcd'
    responses.add(
        responses.GET, 
        expected_submit_url(collection.id),
        status=200, 
        json=expected_job(collection.id, job_id)
    )

    actual_job_id = Client(should_validate_auth=False).submit(request)

    assert len(responses.calls) == 1
    assert responses.calls[0].request is not None
    assert urllib.parse.unquote(responses.calls[0].request.url) == expected_full_submit_url(request)
    assert actual_job_id == job_id


def test_with_invalid_request():
    collection = Collection(id='C333666999-EOSDIS')
    request = Request(
        collection=collection,
        spatial=BBox(-190, -100, 100, 190)
    )

    with pytest.raises(Exception):
        Client(should_validate_auth=False).submit(request)


@responses.activate
def test_status():
    collection = Collection(id='C333666999-EOSDIS')
    job_id = '21469294-d6f7-42cc-89f2-c81990a5d7f4'
    exp_job = expected_job(collection.id, job_id)
    expected_status = {
        'progress': exp_job['progress'],
        'status': exp_job['status'],
        'message': exp_job['message'],
        'createdAt': exp_job['createdAt'],
        'updatedAt': exp_job['updatedAt'],
        'request': exp_job['request'],
        'numInputGranules': exp_job['numInputGranules']}
    responses.add(
        responses.GET,
        expected_status_url(job_id),
        status=200,
        json=exp_job
    )
    responses.add(
        responses.GET,
        expected_status_url(job_id),
        status=200,
        json=exp_job
    )

    actual_status = []
    actual_status.append(Client(should_validate_auth=False).status(job_id, progress_only=False))
    actual_status.append(Client(should_validate_auth=False).status(job_id, progress_only=True))

    assert len(responses.calls) == 2
    assert responses.calls[0].request is not None
    assert urllib.parse.unquote(responses.calls[0].request.url) == expected_status_url(job_id)
    assert urllib.parse.unquote(responses.calls[1].request.url) == expected_status_url(job_id)
    assert actual_status[0] == expected_status
    assert actual_status[1] == expected_status['progress']
