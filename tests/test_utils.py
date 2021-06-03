import time

from sider.utils import time_it


def test_sider_utils(capsys):
    with time_it("foo-bar", iterations=100):
        pass

    captured = capsys.readouterr()
    assert "µs/it" in captured.out
    assert "foo-bar" in captured.out

    with time_it("bar-baz"):
        pass

    captured = capsys.readouterr()
    assert "µs/it" not in captured.out
    assert "bar-baz" in captured.out
