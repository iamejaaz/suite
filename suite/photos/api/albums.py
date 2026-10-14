import json

import frappe
from pypika import Order

from suite.drive.api.list import DriveFavourite
from suite.drive.api.permissions import user_has_permission
from suite.drive.utils import FILE_FIELDS, GENERAL_USER, GROUP_PREFIX, get_principals
from suite.photos.api.photos import PAGE_SIZE, File, media_query

Album = frappe.qb.DocType("Photo Album")
AlbumItem = frappe.qb.DocType("Photo Album Item")
AlbumShare = frappe.qb.DocType("Photo Album Share")
PUBLIC = ""
NO_ACCESS = {"read": 0, "write": 0, "share": 0, "owner": 0}


def album_access(album, user=None):
    user = user or frappe.session.user
    owner = frappe.db.get_value("Photo Album", album, "owner")
    if not owner:
        return NO_ACCESS
    if user == owner or user == "Administrator":
        return {"read": 1, "write": 1, "share": 1, "owner": int(user == owner)}
    rows = frappe.get_all(
        "Photo Album Share",
        filters={"album": album, "user": ["in", get_principals(user)]},
        fields=["read", "write"],
    )
    write = int(any(row.write for row in rows))
    read = int(write or any(row.read for row in rows))
    return {"read": read, "write": write, "share": write, "owner": 0}


def _require(album, ptype):
    if not album_access(album)[ptype]:
        frappe.throw("You don't have access to this album.", frappe.PermissionError)


def readable_albums(user=None):
    user = user or frappe.session.user
    shared = frappe.get_all(
        "Photo Album Share",
        filters={"user": ["in", get_principals(user)], "read": 1},
        pluck="album",
        distinct=True,
    )
    own = frappe.get_all("Photo Album", filters={"owner": user}, pluck="name")
    return list({*own, *shared})


def grants_read(doc, user):
    principals = get_principals(user)
    shared = frappe.qb.from_(AlbumShare).select(AlbumShare.album).where(AlbumShare.user.isin(principals))
    query = (
        frappe.qb.from_(AlbumItem)
        .join(Album)
        .on(Album.name == AlbumItem.album)
        .select(AlbumItem.name)
        .where(AlbumItem.file == doc.name)
        .where((Album.owner == user) | Album.name.isin(shared))
        .limit(1)
    )
    return bool(query.run())


def _summaries(names):
    rows = frappe.get_all(
        "Photo Album",
        filters={"name": ["in", names or [""]]},
        fields=["name", "title", "cover", "owner", "modified"],
        order_by="modified desc",
    )
    general = dict(
        frappe.get_all(
            "Photo Album Share",
            filters={"album": ["in", names or [""]], "user": ["in", [PUBLIC, GENERAL_USER]]},
            fields=["album", "user"],
            as_list=True,
        )
    )
    shared_with_people = set(
        frappe.get_all(
            "Photo Album Share",
            filters={"album": ["in", names or [""]], "user": ["not in", [PUBLIC, GENERAL_USER]]},
            pluck="album",
        )
    )
    for row in rows:
        items = frappe.get_all(
            "Photo Album Item", filters={"album": row.name}, pluck="file", order_by="creation desc"
        )
        row.count = len(items)
        if not row.cover or row.cover not in items:
            row.cover = items[0] if items else None
        row.owner_name = frappe.db.get_value("User", row.owner, "full_name")
        row.general = "public" if general.get(row.name) == PUBLIC else "site" if row.name in general else None
        row.shared = bool(row.general) or row.name in shared_with_people
    return rows


@frappe.whitelist()
def albums():
    return _summaries(frappe.get_all("Photo Album", filters={"owner": frappe.session.user}, pluck="name"))


@frappe.whitelist()
def shared_albums():
    user = frappe.session.user
    names = frappe.get_all(
        "Photo Album Share",
        filters={"user": ["in", [p for p in get_principals(user) if p != PUBLIC]], "read": 1},
        pluck="album",
        distinct=True,
    )
    rows = [row for row in _summaries(names) if row.owner != user]
    for row in rows:
        row.access = album_access(row.name, user)
    return rows


@frappe.whitelist(allow_guest=True)
def get_album(album: str):
    access = album_access(album)
    if not access["read"]:
        frappe.throw("You don't have access to this album.", frappe.PermissionError)
    summary = _summaries([album])[0]
    summary.access = access
    return summary


@frappe.whitelist(allow_guest=True)
def album_photos(album: str, start: int = 0, limit: int | None = None):
    _require(album, "read")
    start, limit = int(start or 0), int(limit or PAGE_SIZE)
    user = frappe.session.user
    query = (
        media_query(check_permission=False, archived=None)
        .select(*FILE_FIELDS)
        .join(AlbumItem)
        .on((AlbumItem.file == File.name) & (AlbumItem.album == album))
        .select(AlbumItem.owner.as_("added_by"))
        .left_join(DriveFavourite)
        .on((DriveFavourite.entity == File.name) & (DriveFavourite.user == user))
        .select(DriveFavourite.name.as_("is_favourite"))
        .orderby(File.name, order=Order.asc)
        .limit(limit + 1)
        .offset(start)
    )
    rows = query.run(as_dict=True)
    for row in rows:
        row["file_url"] = None
        row["read"] = 1
        row["write"] = int(user != "Guest" and row["owner"] == user)
    return {"rows": rows[:limit], "has_next": len(rows) > limit, "next_start": start + min(len(rows), limit)}


@frappe.whitelist()
def create_album(title: str, files: list[str] | str | None = None):
    album = frappe.get_doc({"doctype": "Photo Album", "title": title.strip()}).insert(ignore_permissions=True)
    if files:
        add_to_album(album.name, files)
    return album.name


@frappe.whitelist()
def rename_album(album: str, title: str):
    _require(album, "write")
    frappe.db.set_value("Photo Album", album, "title", title.strip())


@frappe.whitelist()
def set_cover(album: str, file: str):
    _require(album, "write")
    if not frappe.db.exists("Photo Album Item", {"album": album, "file": file}):
        frappe.throw("That photo is not in this album.")
    frappe.db.set_value("Photo Album", album, "cover", file)


@frappe.whitelist()
def delete_album(album: str):
    _require(album, "owner")
    frappe.db.delete("Photo Album Item", {"album": album})
    frappe.db.delete("Photo Album Share", {"album": album})
    frappe.delete_doc("Photo Album", album, ignore_permissions=True)


@frappe.whitelist()
def leave_album(album: str):
    frappe.db.delete("Photo Album Share", {"album": album, "user": frappe.session.user})


@frappe.whitelist()
def add_to_album(album: str, files: list[str] | str):
    _require(album, "write")
    existing = set(frappe.get_all("Photo Album Item", filters={"album": album}, pluck="file"))
    for file in _as_list(files):
        if file in existing or not user_has_permission(file, "read"):
            continue
        frappe.get_doc({"doctype": "Photo Album Item", "album": album, "file": file}).insert(
            ignore_permissions=True
        )
    frappe.db.set_value("Photo Album", album, "modified", frappe.utils.now_datetime())


@frappe.whitelist()
def remove_from_album(album: str, files: list[str] | str):
    _require(album, "write")
    frappe.db.delete("Photo Album Item", {"album": album, "file": ["in", _as_list(files)]})


@frappe.whitelist()
def get_shared_with_list(entity: str):
    _require(entity, "share")
    rows = frappe.get_all(
        "Photo Album Share",
        filters={"album": entity, "user": ["not in", [PUBLIC, GENERAL_USER]]},
        fields=["user", "read", "write"],
        order_by="user",
    )
    owner = frappe.db.get_value("Photo Album", entity, "owner")
    rows.insert(0, frappe._dict(user=owner, read=1, write=1))
    for row in rows:
        if row.user.startswith(GROUP_PREFIX):
            row.is_group = 1
            row.full_name = row.user[len(GROUP_PREFIX) :]
        elif info := frappe.db.get_value(
            "User", row.user, ["user_image", "full_name", "email"], as_dict=True
        ):
            row.update(info)
    return rows


@frappe.whitelist(allow_guest=True)
def get_general_access(entity: str):
    _require(entity, "read")
    rows = {
        row.user: row
        for row in frappe.get_all(
            "Photo Album Share",
            filters={"album": entity, "user": ["in", [PUBLIC, GENERAL_USER]]},
            fields=["user", "read", "write"],
        )
    }
    for user, kind in ((PUBLIC, "public"), (GENERAL_USER, "site")):
        if row := rows.get(user):
            return {"type": kind, "read": 1, "write": row.write}
    return {"type": "restricted", "read": 0, "write": 0}


@frappe.whitelist()
def update_access(
    entity_name: str, user: str = PUBLIC, read: int = 1, write: int = 0, method: str = "share", **kwargs
):
    _require(entity_name, "share")
    if user == frappe.db.get_value("Photo Album", entity_name, "owner"):
        frappe.throw("The owner always has access.")
    general = user in (PUBLIC, GENERAL_USER)
    targets = [PUBLIC, GENERAL_USER] if general else [user]
    frappe.db.delete("Photo Album Share", {"album": entity_name, "user": ["in", targets]})
    if method == "unshare":
        return
    write = int(frappe.parse_json(write) or 0)
    if write and user == PUBLIC:
        frappe.throw("Anyone with the link can only view.")
    frappe.get_doc(
        {"doctype": "Photo Album Share", "album": entity_name, "user": user, "read": 1, "write": write}
    ).insert(ignore_permissions=True)


def _as_list(value):
    return json.loads(value) if isinstance(value, str) else value
