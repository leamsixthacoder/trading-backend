from uuid import UUID

import psycopg2
from fastapi import APIRouter, HTTPException

from app.database import get_cursor
from app.schemas import (
    AccountGroupCreate,
    AccountGroupMemberCreate,
    AccountGroupMemberOut,
    AccountGroupOut,
    AccountGroupUpdate,
    AccountOut,
)

router = APIRouter(prefix="/account-groups", tags=["account-groups"])


def _require_group_exists(cur, group_id: UUID) -> None:
    cur.execute("SELECT 1 FROM account_groups WHERE id = %s", (str(group_id),))
    if cur.fetchone() is None:
        raise HTTPException(status_code=404, detail="Account group not found")


@router.post("", response_model=AccountGroupOut, status_code=201)
def create_account_group(body: AccountGroupCreate):
    with get_cursor() as cur:
        try:
            cur.execute(
                "INSERT INTO account_groups (name) VALUES (%s) RETURNING id, name, created_at",
                (body.name,),
            )
        except psycopg2.errors.UniqueViolation:
            raise HTTPException(status_code=409, detail=f"A group named '{body.name}' already exists")
        return cur.fetchone()


@router.get("", response_model=list[AccountGroupOut])
def list_account_groups():
    with get_cursor() as cur:
        cur.execute("SELECT id, name, created_at FROM account_groups ORDER BY name")
        return cur.fetchall()


@router.patch("/{group_id}", response_model=AccountGroupOut)
def update_account_group(group_id: UUID, body: AccountGroupUpdate):
    with get_cursor() as cur:
        try:
            cur.execute(
                "UPDATE account_groups SET name = %s WHERE id = %s RETURNING id, name, created_at",
                (body.name, str(group_id)),
            )
        except psycopg2.errors.UniqueViolation:
            raise HTTPException(status_code=409, detail=f"A group named '{body.name}' already exists")
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Account group not found")
        return row


@router.delete("/{group_id}", status_code=204)
def delete_account_group(group_id: UUID):
    with get_cursor() as cur:
        cur.execute("DELETE FROM account_groups WHERE id = %s", (str(group_id),))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Account group not found")


@router.get("/{group_id}/accounts", response_model=list[AccountOut])
def list_group_accounts(group_id: UUID):
    with get_cursor() as cur:
        _require_group_exists(cur, group_id)
        cur.execute(
            "SELECT a.id, a.label, a.account_type, a.provider, a.capital_base, a.status, "
            "a.created_at, a.closed_at FROM accounts a "
            "JOIN account_group_members m ON m.account_id = a.id "
            "WHERE m.group_id = %s ORDER BY a.label",
            (str(group_id),),
        )
        return cur.fetchall()


@router.post("/{group_id}/accounts", response_model=AccountGroupMemberOut, status_code=201)
def add_group_member(group_id: UUID, body: AccountGroupMemberCreate):
    with get_cursor() as cur:
        _require_group_exists(cur, group_id)
        cur.execute("SELECT 1 FROM accounts WHERE id = %s", (str(body.account_id),))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Account not found")
        try:
            cur.execute(
                "INSERT INTO account_group_members (group_id, account_id) VALUES (%s, %s) "
                "RETURNING group_id, account_id, added_at",
                (str(group_id), str(body.account_id)),
            )
        except psycopg2.errors.UniqueViolation:
            raise HTTPException(status_code=409, detail="Account is already in this group")
        return cur.fetchone()


@router.delete("/{group_id}/accounts/{account_id}", status_code=204)
def remove_group_member(group_id: UUID, account_id: UUID):
    with get_cursor() as cur:
        cur.execute(
            "DELETE FROM account_group_members WHERE group_id = %s AND account_id = %s",
            (str(group_id), str(account_id)),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Account is not a member of this group")
