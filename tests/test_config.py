from hamcrest import assert_that, has_entries, has_entry, contains
from io import StringIO
from ci import parse_config

defaults = {
    'python': {
        'default': {
            'image': 'python',
            'before_install': [],
            'install': [],
            'before_script': [],
            'script': [],
            'after_script': [],
            'after_success': [],
            'after_failure': []
        }
    }
}

defaults['python']['3.3'] = dict(defaults['python']['default'])
defaults['python']['3.3']['image'] = 'python:3.3'

defaults['python']['3.4'] = dict(defaults['python']['default'])
defaults['python']['3.4']['image'] = 'python:3.4'


def test_populates_with_defaults():
    raw = StringIO('language: python\n')
    config = parse_config(raw, defaults)

    assert_that(config, contains(has_entries({
        'language': 'python',
        'image': 'python'
    })))


def test_config_overrides():
    raw = StringIO(
        '''
        language: python
        script: nosetests
        '''
    )

    config = parse_config(raw, defaults)

    assert_that(config, contains(has_entry('script', ['nosetests'])))


def test_cant_override_image():
    raw = StringIO(
        '''
        language: python
        image: node
        '''
    )

    config = parse_config(raw, defaults)

    assert_that(config, contains(has_entry('image', 'python')))


def test_matrix_config_language():
    raw = StringIO(
        '''
        language: python
        python:
          - "3.3"
          - "3.4"
        image: node
        '''
    )

    config = parse_config(raw, defaults)

    assert_that(config, contains(
        has_entry('image', 'python:3.3'),
        has_entry('image', 'python:3.4')
    ))


def test_matrix_config_environment():
    raw = StringIO(
        '''
        language: python
        environment:
          - FOO=bar
          - FOO=baz
        image: node
        '''
    )

    config = parse_config(raw, defaults)

    assert_that(config, contains(
        has_entry('environment', 'FOO=bar'),
        has_entry('environment', 'FOO=baz')
    ))


def test_matrix_config_product():
    raw = StringIO(
        '''
        language: python
        python:
          - "3.3"
          - "3.4"
        environment:
          - FOO=bar
          - FOO=baz
        image: node
        '''
    )

    config = parse_config(raw, defaults)

    assert_that(config, contains(
        has_entries(image='python:3.3', environment='FOO=bar'),
        has_entries(image='python:3.3', environment='FOO=baz'),
        has_entries(image='python:3.4', environment='FOO=bar'),
        has_entries(image='python:3.4', environment='FOO=baz')
    ))
