"""Main module."""
from copy import deepcopy
from datetime import datetime
from difflib import Differ
from io import StringIO
from typing import IO, Iterable, AnyStr

from datadiff.tools import assert_equal
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap


class MVYamlVersionNotFoundException(Exception):
    pass


class MVYamlFileException(Exception):
    pass


def as_yaml(data: Iterable) -> AnyStr:
    yaml = YAML()
    output = StringIO()
    yaml.dump(data, output)
    return output.getvalue()


class MVYaml(object):
    protected_keys = ('__current', '__type', )

    def __init__(self, base64=False):
        self._b64 = base64
        self._raw = CommentedMap()
        self._yaml = YAML()
        self._curr_version = None
        self._curr_data = None
        self._create()

    def _create(self):
        tag = self._make_tag()
        self._raw[tag] = CommentedMap()
        self._raw.insert(0, '__current', tag, 'current version')
        self._raw.insert(1, '__type', None, 'base64 if value are base64')
        self._commit(tag=tag, comment='Initial version')

    def import_yaml(self, file: AnyStr = None, stream: AnyStr = None):
        data = None
        if file:
            with open(file, 'r') as fp:
                data = fp.read()
        imported_data = self._yaml.load(data or stream)
        self.override(imported_data)
        return self

    def load(self, file_handler: AnyStr = None, stream_data: AnyStr = None):
        data = None
        if file_handler:
            with open(file_handler, 'r') as fp:
                data = fp.read()
        self._raw = self._yaml.load(data or stream_data)
        if self.protected_keys not in self._raw.keys():
            raise MVYamlFileException(f'Not a valid mvyaml file. Perhaps is a yaml you want to import with '
                                      f'import_yaml()?')
        return self

    def write(self, file_handler: IO = None, comment: AnyStr = None) -> [AnyStr, None]:
        if not self._raw:
            return
        if self._has_changes():
            self._commit(comment=comment)
        output = file_handler or StringIO()
        self._yaml.dump(self._raw, output)
        return output.getvalue() if not file_handler else None

    @property
    def versions(self):
        if not self._raw:
            return []
        return [k for k in self._raw.keys() if k not in self.protected_keys]

    @property
    def current(self):
        return self._raw['__current']

    @property
    def data(self):
        if not self._curr_data:
            self._curr_data = deepcopy(self._raw[self._curr_version or self.current])
        return self._curr_data

    def with_version(self, version: str = '__current'):
        if version not in self.versions:
            raise MVYamlVersionNotFoundException(f'version {version} not found')
        self._curr_version = version
        self._curr_data = None
        return self

    @staticmethod
    def _make_tag() -> str:
        d = datetime.utcnow().isoformat()
        return d

    def override(self, data: [Iterable]):
        self._curr_data = CommentedMap()
        self._curr_data.update(data)
        self._commit(comment='Overridden')
        return self

    def _commit(self, *args, **kwargs):
        return self._commit_head(*args, **kwargs)

    def _commit_head(self, tag: AnyStr = None, comment: AnyStr = None):
        """
        apply the modifications on curr_data to the underling opened version
        and create a new tag
        """
        commented_map = CommentedMap()
        commented_map.update(self._curr_data or self.data)
        if tag:
            self._raw[tag] = commented_map
            self._raw['__current'] = tag
        else:
            new_tag = self._make_tag()
            self._raw.insert(2, new_tag, commented_map, comment=comment)
            self._raw['__current'] = new_tag
        self._curr_version = None
        self._curr_data = None
        return self

    def _commit_tail(self, tag: AnyStr = None, comment: AnyStr = None):
        """
        apply the modifications on curr_data to the underling opened version
        and create a new tag
        """
        commented_map = CommentedMap()
        commented_map.update(self._curr_data or self.data)
        if tag:
            self._raw[tag] = commented_map
            self._raw['__current'] = tag
        else:
            new_tag = self._make_tag()
            self._raw.insert(len(self._raw.keys()), new_tag, commented_map, comment=comment)
            self._raw['__current'] = new_tag
        self._curr_version = None
        self._curr_data = None
        return self

    def _has_changes(self):
        orig = self._raw[self._curr_version or self.current]
        current = self._curr_data or self.data
        try:
            assert_equal(orig, current)
        except AssertionError:
            return True
        return False

    @property
    def changes(self) -> AnyStr:
        if not self._has_changes():
            return ''
        yaml_orig = as_yaml(self._raw[self._curr_version or self.current])
        yaml_curr = as_yaml(self._curr_data)
        differ = Differ()
        result = list(differ.compare(
            yaml_orig.splitlines(),
            yaml_curr.splitlines()
        ))
        return '\n'.join(result)

    def set_current(self, version_label: AnyStr):
        if version_label not in self.versions:
            raise MVYamlVersionNotFoundException(f'request version [{version_label}] not found')
        self._raw['__current'] = version_label
        self.with_version(version_label)
        return self
