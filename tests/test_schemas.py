"""Tests for new schema models — ExecuteMethodResult, DiscoverActionsResult, ModelAction."""

import pytest

from next_mcp_odoo.schemas import (
    DiscoverActionsResult,
    ExecuteMethodResult,
    ModelAction,
)


class TestExecuteMethodResult:
    def test_success_result(self):
        r = ExecuteMethodResult(
            success=True,
            model="account.move",
            method="action_post",
            ids=[42],
            result=True,
            message="Successfully called account.move.action_post() on 1 record(s)",
        )
        assert r.success is True
        assert r.model == "account.move"
        assert r.method == "action_post"
        assert r.ids == [42]
        assert r.result is True

    def test_failure_result(self):
        r = ExecuteMethodResult(
            success=False,
            model="account.move",
            method="action_post",
            ids=None,
            result=None,
            message="Method execution failed: access denied",
        )
        assert r.success is False
        assert r.ids is None
        assert r.result is None

    def test_result_can_be_dict(self):
        r = ExecuteMethodResult(
            success=True,
            model="sale.order",
            method="action_quotation_send",
            ids=[7],
            result={"type": "ir.actions.act_window"},
            message="Done",
        )
        assert isinstance(r.result, dict)

    def test_result_can_be_list(self):
        r = ExecuteMethodResult(
            success=True,
            model="res.partner",
            method="name_get",
            ids=[1, 2],
            result=[[1, "Partner A"], [2, "Partner B"]],
            message="Done",
        )
        assert isinstance(r.result, list)

    def test_no_ids(self):
        r = ExecuteMethodResult(
            success=True,
            model="ir.module.module",
            method="upgrade_module",
            ids=None,
            result=None,
            message="Module upgraded",
        )
        assert r.ids is None


class TestModelAction:
    def test_basic_action(self):
        action = ModelAction(
            name="action_post",
            label="Post / Validate Invoice",
            kind="server_action",
            binding_model="account.move",
        )
        assert action.name == "action_post"
        assert action.label == "Post / Validate Invoice"
        assert action.kind == "server_action"
        assert action.binding_model == "account.move"

    def test_action_without_binding_model(self):
        action = ModelAction(
            name="message_post",
            label="Post message in chatter",
            kind="orm_method",
            binding_model=None,
        )
        assert action.binding_model is None

    def test_window_action_kind(self):
        action = ModelAction(
            name="open_sale_orders",
            label="Open Sale Orders",
            kind="window_action",
            binding_model="sale.order",
        )
        assert action.kind == "window_action"


class TestDiscoverActionsResult:
    def test_basic_result(self):
        actions = [
            ModelAction(name="action_post", label="Validate", kind="server_action"),
            ModelAction(name="message_post", label="Post Message", kind="orm_method"),
        ]
        result = DiscoverActionsResult(
            model="account.move",
            actions=actions,
            total=2,
            note="Call via execute_method(model='account.move', ...)",
        )
        assert result.model == "account.move"
        assert result.total == 2
        assert len(result.actions) == 2

    def test_empty_actions(self):
        result = DiscoverActionsResult(
            model="unknown.model",
            actions=[],
            total=0,
            note="No actions found",
        )
        assert result.total == 0
        assert result.actions == []

    def test_action_kinds(self):
        actions = [
            ModelAction(name="a", label="A", kind="server_action"),
            ModelAction(name="b", label="B", kind="window_action"),
            ModelAction(name="c", label="C", kind="orm_method"),
        ]
        result = DiscoverActionsResult(model="x", actions=actions, total=3, note="")
        kinds = {a.kind for a in result.actions}
        assert kinds == {"server_action", "window_action", "orm_method"}
