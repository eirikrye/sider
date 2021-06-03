from sider.utils import construct_command


def test_bench_construct(benchmark):
    benchmark(construct_command, b"A", b"B", b"C")
