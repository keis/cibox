import mock
import logging
from hamcrest import assert_that
from matchmock import called_once_with
from ci import execute


def test_expected_client_calls():
    container = {'Id': 'zoidberg'}
    handle = {'Id': 'execute'}
    info = {'ExitCode': 0}
    cmd = 'command'

    client = mock.Mock()
    client.exec_create.return_value = handle
    client.exec_start.return_value = []
    client.exec_inspect.return_value = info

    execute(client, container, cmd, logging.getLogger('test-execute'))

    assert_that(
        client.exec_create,
        called_once_with(container='zoidberg',
                         cmd=['/bin/bash', '-c', 'command'])
    )

    assert_that(
        client.exec_start,
        called_once_with(exec_id='execute')
    )

    assert_that(
        client.exec_inspect,
        called_once_with(exec_id='execute')
    )
