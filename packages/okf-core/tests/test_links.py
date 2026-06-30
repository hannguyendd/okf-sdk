from okf_core import rewrite_links, strip_links


def test_inbound_relative_same_dir_repointed(tmp_path):
    body = "see [o](orders.md)"
    out = rewrite_links(body, tmp_path, tmp_path, tmp_path, {"orders": "sales"})
    assert out == "see [o](sales.md)"


def test_inbound_relative_into_subdir(tmp_path):
    out = rewrite_links(
        "[o](orders.md)", tmp_path, tmp_path, tmp_path, {"orders": "models/orders"}
    )
    assert out == "[o](models/orders.md)"


def test_inbound_relative_from_subdir_linker(tmp_path):
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    out = rewrite_links(
        "[o](../tables/orders.md)",
        metrics,
        metrics,
        tmp_path,
        {"tables/orders": "models/orders"},
    )
    assert out == "[o](../models/orders.md)"


def test_inbound_absolute_stays_absolute(tmp_path):
    out = rewrite_links(
        "[o](/tables/orders.md)",
        tmp_path,
        tmp_path,
        tmp_path,
        {"tables/orders": "models/orders"},
    )
    assert out == "[o](/models/orders.md)"


def test_anchor_preserved(tmp_path):
    out = rewrite_links(
        "[o](orders.md#schema)", tmp_path, tmp_path, tmp_path, {"orders": "sales"}
    )
    assert out == "[o](sales.md#schema)"


def test_external_and_out_of_bundle_untouched(tmp_path):
    body = "[x](https://e.com/page.md) [y](../outside.md)"
    out = rewrite_links(body, tmp_path, tmp_path, tmp_path, {"orders": "sales"})
    assert out == body


def test_unrelated_links_untouched_when_dir_unchanged(tmp_path):
    # not in id_map and dir unchanged -> byte-for-byte preserved (incl. ./ style)
    body = "[a](./basics.md) [b](other.md)"
    out = rewrite_links(body, tmp_path, tmp_path, tmp_path, {"orders": "sales"})
    assert out == body


def test_moved_doc_relative_links_recomputed(tmp_path):
    tables = tmp_path / "tables"
    models = tmp_path / "models"
    tables.mkdir()
    out = rewrite_links(
        "[c](customers.md)",
        tables,
        models,
        tmp_path,
        {"tables/orders": "models/orders"},
    )
    assert out == "[c](../tables/customers.md)"


def test_moved_doc_absolute_links_unchanged(tmp_path):
    tables = tmp_path / "tables"
    models = tmp_path / "models"
    tables.mkdir()
    out = rewrite_links(
        "[c](/tables/customers.md)",
        tables,
        models,
        tmp_path,
        {"tables/orders": "models/orders"},
    )
    assert out == "[c](/tables/customers.md)"


def test_noop_returns_equal_body(tmp_path):
    body = "no md links [text](http://x) here"
    assert rewrite_links(body, tmp_path, tmp_path, tmp_path, {}) == body


def test_strip_relative_link_keeps_label(tmp_path):
    out = strip_links("see [Orders](orders.md) now", tmp_path, tmp_path, {"orders"})
    assert out == "see Orders now"


def test_strip_absolute_link_keeps_label(tmp_path):
    out = strip_links(
        "[Orders](/tables/orders.md)", tmp_path, tmp_path, {"tables/orders"}
    )
    assert out == "Orders"


def test_strip_drops_anchor(tmp_path):
    out = strip_links("[Orders](orders.md#schema)", tmp_path, tmp_path, {"orders"})
    assert out == "Orders"


def test_strip_only_targets_in_set(tmp_path):
    body = "[O](orders.md) and [C](customers.md)"
    out = strip_links(body, tmp_path, tmp_path, {"orders"})
    assert out == "O and [C](customers.md)"


def test_strip_id_not_in_set_untouched(tmp_path):
    body = "[C](customers.md)"
    assert strip_links(body, tmp_path, tmp_path, {"orders"}) == body


def test_strip_external_and_out_of_bundle_untouched(tmp_path):
    body = "[x](https://e.com/page.md) [y](../outside.md)"
    assert strip_links(body, tmp_path, tmp_path, {"orders"}) == body


def test_strip_multiple_occurrences(tmp_path):
    body = "[O](orders.md) ... [Orders again](orders.md#x)"
    out = strip_links(body, tmp_path, tmp_path, {"orders"})
    assert out == "O ... Orders again"


def test_strip_from_subdir_resolves_parent_target(tmp_path):
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    out = strip_links(
        "[o](../tables/orders.md)", metrics, tmp_path, {"tables/orders"}
    )
    assert out == "o"


def test_strip_noop_returns_equal_body(tmp_path):
    body = "no md links [text](http://x) here"
    assert strip_links(body, tmp_path, tmp_path, {"orders"}) == body
