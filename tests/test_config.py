from hamcrest import assert_that, has_entry
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


def test_populates_with_defaults():
    raw = StringIO('language: python\n')
    config = parse_config(raw, defaults)

    assert_that(config, has_entry('language', 'python'))
    assert_that(config, has_entry('image', 'python'))


def test_config_overrides():
    raw = StringIO(
        '''
        language: python
        script: nosetests
        '''
    )

    config = parse_config(raw, defaults)

    assert_that(config, has_entry('script', ['nosetests']))


def test_cant_override_image():
    raw = StringIO(
        '''
        language: python
        image: node
        '''
    )

    config = parse_config(raw, defaults)

    assert_that(config, has_entry('image', 'python'))
