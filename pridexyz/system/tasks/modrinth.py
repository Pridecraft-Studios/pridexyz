from enum import Enum
from pathlib import Path
from typing import List

import typer

from pridexyz.markdown import markdown_with_frontmatter_to_dict, appy_modrinth_markdown_template
from pridexyz.modrinth.api import ModrinthAPI, ModrinthAPIError, cut_game_versions_until
from pridexyz.modrinth.types import (NewProject, ProjectType, SideSupport, ProjectUpdate,
                                     GalleryImage, NewVersion, VersionType, DictKV, VersionUpdate)
from pridexyz.system.config import settings, logger

app = typer.Typer(help="Manage Modrinth projects (Create, Update, Publish, Sync)")

class UpdateMode(str, Enum):
    ALL = "all"
    ICON = "icon"
    GALLERY = "gallery"
    DATA = "data"
    BODY = "body"


class CleanupMode(str, Enum):
    NON_DRAFT = "non-draft"
    PUBLISHED = "published"


def get_api() -> ModrinthAPI:
    if not settings.MODRINTH_TOKEN or not settings.MODRINTH_API_URL:
        logger.error("Missing Modrinth configuration in .env")
        raise typer.Exit(1)

    return ModrinthAPI(
        token=settings.MODRINTH_TOKEN,
        api_url=settings.MODRINTH_API_URL,
        user_agent=f"Pridecraft-Studios/pridexyz ({settings.BUILD_USER})",
        enable_debug_logging=settings.DEBUG_LOGGING
    )


def load_project_data(project_dir: Path) -> dict:
    md_file = project_dir / "modrinth.md"
    if not md_file.is_file():
        logger.debug(f"[{project_dir.name}] Missing 'modrinth.md' file.")
        return {}
    return markdown_with_frontmatter_to_dict(md_file)


def fetch_org_projects(api: ModrinthAPI) -> tuple[dict, dict]:
    lookup = settings.get_org_lookup()
    projects = {}

    for _, org_id in lookup.items():
        try:
            projs = api.get_organization_projects(org_id)
            for p in projs:
                projects[p["slug"]] = p
        except ModrinthAPIError as e:
            logger.error(f"Failed to fetch organization projects: {e}")

    return projects, lookup


def get_game_versions_until_cutoff(cutoff_version: str, versions: List[DictKV]) -> List[str]:
    cut_versions = cut_game_versions_until(cutoff_version, versions)
    return [version["version"] for version in cut_versions]


def check_files(project_dir: Path, data: dict) -> bool:
    required = [data.get("version_file"), data.get("icon_file"), data.get("gallery_file")]
    missing = [f for f in required if f and not (project_dir / f).is_file()]

    if missing:
        logger.warning(f"[{project_dir.name}] Missing required file(s): {', '.join(str(m) for m in missing)}")
        return False
    return True


@app.command()
def check():
    if not settings.BUILD_DIR.is_dir():
        logger.error("Build directory missing. Run 'build' first.")
        raise typer.Exit(1)

    api = get_api()
    existing_projects, _ = fetch_org_projects(api)

    total, files_ok, modrinth_ok = 0, 0, 0

    logger.info("Starting check task...")

    for project_dir in settings.BUILD_DIR.iterdir():
        if not project_dir.is_dir(): continue

        data = load_project_data(project_dir)
        if not data: continue

        total += 1
        slug = data.get("slug", "???")

        logger.info(f"[{project_dir.name}] Checking...")

        if check_files(project_dir, data):
            files_ok += 1

        if slug in existing_projects:
            logger.info(f"[{project_dir.name}] Exists on Modrinth.")
            modrinth_ok += 1
        else:
            logger.warning(f"[{project_dir.name}] Not found on Modrinth.")

    logger.info(f"Checked {total} projects: {files_ok} valid locally, {modrinth_ok} exist remotely.")


@app.command()
def create():
    api = get_api()
    existing_projects, org_lookup = fetch_org_projects(api)
    queue = []

    for project_dir in settings.BUILD_DIR.iterdir():
        if not project_dir.is_dir(): continue

        data = load_project_data(project_dir)
        if not data: continue

        slug = data.get("slug")
        if slug in existing_projects:
            logger.info(f"[{project_dir.name}] Project already exists, skipping.")
            continue

        if not check_files(project_dir, data):
            continue

        # Closure for parallel execution
        def _create_task(d=data, p_dir=project_dir):
            dir_name = p_dir.name
            try:
                org_id = org_lookup.get(d["org_id_source"])
                result = api.create_project(
                    NewProject(
                        slug=d["slug"],
                        title=d["name"],
                        description="......",
                        categories=[],
                        additional_categories=[],
                        project_type=ProjectType.RESOURCEPACK,
                        organization_id=org_id,
                        license_id=d["license_id"],
                        client_side=SideSupport.REQUIRED,
                        server_side=SideSupport.UNSUPPORTED,
                        body="......"
                    ),
                    icon_path=p_dir / d["icon_file"]
                )
                return {"slug": d["slug"], "dir_name": dir_name, "success": True, "result": result}
            except ModrinthAPIError as e:
                return {"slug": d["slug"], "dir_name": dir_name, "success": False, "ModrinthAPIError": e}

        logger.info(f"[{project_dir.name}] Queued for creation...")
        queue.append(_create_task)

    if queue:
        results = api.parallel_requests(queue)
        for res in results:
            if res["success"]:
                logger.info(f"[{res.get('dir_name')}] Created successfully.")
            else:
                logger.error(f"[{res.get('dir_name')}] Failed: {res.get('ModrinthAPIError')}")


@app.command()
def update(mode: UpdateMode = typer.Argument(..., help="What to update: icon, gallery, data, body, or all")):
    api = get_api()
    existing_projects, _ = fetch_org_projects(api)
    queue = []

    for project_dir in settings.BUILD_DIR.iterdir():
        if not project_dir.is_dir(): continue

        data = load_project_data(project_dir)
        if not data: continue

        slug = data.get("slug")
        project = existing_projects.get(slug)

        if not project:
            logger.warning(f"[{project_dir.name}] Project not found on Modrinth, skipping.")
            continue

        def _update_task(d=data, p_dir=project_dir, p=project, m=mode):
            dir_name = p_dir.name
            s = d["slug"]

            try:
                if m in [UpdateMode.ALL, UpdateMode.ICON]:
                    logger.info(f"[{dir_name}] Updating icon...")
                    icon_file = p_dir / d["icon_file"]
                    api.change_project_icon(p["id"], icon_path=icon_file, ext=icon_file.suffix.lstrip("."))

                if m in [UpdateMode.ALL, UpdateMode.GALLERY]:
                    logger.info(f"[{dir_name}] Updating gallery...")
                    gallery_file = p_dir / d["gallery_file"]
                    if p.get("gallery"):
                        try:
                            api.delete_gallery_image(d["gallery_file"], p["gallery"][0]["url"])
                        except Exception:
                            pass
                    api.add_gallery_image(s, GalleryImage(
                        image_path=gallery_file,
                        ext=gallery_file.suffix.lstrip("."),
                        featured=True,
                        title=d["gallery_title"],
                        description=d["gallery_description"]
                    ))

                if m in [UpdateMode.ALL, UpdateMode.DATA, UpdateMode.BODY]:
                    refreshed = api.get_project(s)
                    gallery_url = refreshed["gallery"][0]["url"] if refreshed.get("gallery") else None
                    new_body = appy_modrinth_markdown_template(d["body"], context={"upload_gallery_url": gallery_url})

                    update_payload = ProjectUpdate()

                    if m in [UpdateMode.ALL, UpdateMode.BODY]:
                        logger.info(f"[{dir_name}] Updating body...")
                        update_payload.body = new_body

                    if m in [UpdateMode.ALL, UpdateMode.DATA]:
                        logger.info(f"[{dir_name}] Updating metadata...")
                        update_payload.title = d["name"]
                        update_payload.description = d["summary"]
                        update_payload.categories = d["primary_categories"].split(" ")
                        update_payload.additional_categories = d["additional_categories"].split(" ")
                        update_payload.issues_url = d["issue_url"]
                        update_payload.source_url = d["source_url"]
                        update_payload.discord_url = d["discord_url"]
                        update_payload.license_id = d["license_id"]
                        if not update_payload.body:
                            update_payload.body = new_body

                    api.modify_project(p["id"], update_payload)

                return {"slug": s, "dir_name": dir_name, "success": True}

            except ModrinthAPIError as e:
                return {"slug": s, "dir_name": dir_name, "success": False, "ModrinthAPIError": e}

        logger.info(f"[{project_dir.name}] Queued for update ({mode.value})...")
        queue.append(_update_task)

    if queue:
        results = api.parallel_requests(queue)
        for res in results:
            if not res["success"]:
                logger.error(f"[{res.get('dir_name')}] Update failed: {res.get('ModrinthAPIError')}")
            else:
                logger.info(f"[{res.get('dir_name')}] Update successful.")


@app.command()
def publish():
    api = get_api()
    existing_projects, _ = fetch_org_projects(api)
    game_versions = api.get_game_versions()

    try:
        meta = settings.load_json(settings.META_PATH)
    except Exception:
        return

    queue = []

    for project_dir in settings.BUILD_DIR.iterdir():
        if not project_dir.is_dir(): continue

        data = load_project_data(project_dir)
        if not data: continue

        slug = data.get("slug")
        project = existing_projects.get(slug)

        if not project:
            logger.warning(f"[{project_dir.name}] Not on Modrinth, cannot publish.")
            continue

        def _publish_task(d=data, p_dir=project_dir, proj=project):
            dir_name = p_dir.name
            try:
                raw_name = f"{str(d['name']).replace(meta['redundant_removable_info'], '')} {d['version_version']}"
                version_name = raw_name

                for replaceable, replacement in meta.get("shortenable", {}).items():
                    if len(version_name) > 64:
                        version_name = version_name.replace(replaceable, replacement)
                    else:
                        break

                logger.debug(f"[{d['slug']}] Version name: {version_name}")

                gv = get_game_versions_until_cutoff(d["version_game_version_cutoff"], game_versions)

                result = api.create_version(
                    NewVersion(
                        name=version_name,
                        version_number=d["version_version"],
                        project_id=proj["id"],
                        loaders=["minecraft"],
                        version_type=VersionType.RELEASE,
                        dependencies=[],
                        game_versions=gv
                    ),
                    file_paths=[p_dir / d["version_file"]]
                )
                return {"slug": d["slug"], "dir_name": dir_name, "success": True, "result": result}
            except ModrinthAPIError as e:
                return {"slug": d["slug"], "dir_name": dir_name, "success": False, "ModrinthAPIError": e}

        logger.info(f"[{project_dir.name}] Queued for publish...")
        queue.append(_publish_task)

    if queue:
        results = api.parallel_requests(queue)
        for res in results:
            if res["success"]:
                logger.info(f"[{res.get('dir_name')}] Published successfully.")
            else:
                logger.error(f"[{res.get('dir_name')}] Publish failed: {res.get('ModrinthAPIError')}")


@app.command()
def update_mc_versions():
    api = get_api()
    existing_projects, _ = fetch_org_projects(api)
    game_versions = api.get_game_versions()
    queue = []

    for slug, project in existing_projects.items():
        local_data = None
        local_dir_name = slug

        for p_dir in settings.BUILD_DIR.iterdir():
            if not p_dir.is_dir(): continue
            d = load_project_data(p_dir)
            if d.get("slug") == slug:
                local_data = d
                local_dir_name = p_dir.name
                break

        if not local_data:
            continue

        def _update_vers_task(d=None, p=project, dirname=local_dir_name):
            if d is None:
                d = local_data
            try:
                if isinstance(p.get("versions"), list) and len(p.get("versions")) > 0:
                    vid = p.get("versions")[0]
                else:
                    return {"slug": d["slug"], "success": False, "ModrinthAPIError": "No versions found"}

                gv = get_game_versions_until_cutoff(d["version_game_version_cutoff"], game_versions)
                api.modify_version(vid, VersionUpdate(game_versions=gv))
                return {"slug": d["slug"], "dir_name": dirname, "success": True}
            except ModrinthAPIError as e:
                return {"slug": d["slug"], "dir_name": dirname, "success": False, "ModrinthAPIError": e}

        logger.info(f"[{local_dir_name}] Queued for version list update...")
        queue.append(_update_vers_task)

    if queue:
        results = api.parallel_requests(queue)
        for res in results:
            if res["success"]:
                logger.info(f"[{res.get('dir_name')}] Versions updated.")
            else:
                logger.error(f"[{res.get('dir_name')}] Version update failed: {res.get('ModrinthAPIError')}")


@app.command()
def submit():
    api = get_api()
    existing_projects, _ = fetch_org_projects(api)
    queue = []

    for slug, project in existing_projects.items():
        if project.get("status") == "processing":
            logger.info(f"[{slug}] Already processing.")
            continue

        def _submit_task(s=slug, p=project):
            try:
                api.modify_project(p["id"], ProjectUpdate(status="processing"))
                return {"slug": s, "dir_name": s, "success": True}
            except ModrinthAPIError as e:
                return {"slug": s, "dir_name": s, "success": False, "ModrinthAPIError": e}

        logger.info(f"[{slug}] Queued for submit...")
        queue.append(_submit_task)

    if queue:
        results = api.parallel_requests(queue)
        for res in results:
            if not res["success"]:
                logger.error(f"[{res.get('slug')}] Submit failed: {res.get('ModrinthAPIError')}")
            else:
                logger.info(f"[{res.get('slug')}] Submitted.")


@app.command()
def cleanup(mode: CleanupMode = typer.Argument(..., help="Modes: 'non-draft' (deletes non-draft folders) or 'published' (deletes if version exists)")):
    if not settings.BUILD_DIR.is_dir(): return

    api = get_api()
    existing_projects, _ = fetch_org_projects(api)
    deleted_count = 0

    import shutil

    for project_dir in settings.BUILD_DIR.iterdir():
        if not project_dir.is_dir(): continue

        data = load_project_data(project_dir)
        if not data: continue

        slug = data.get("slug")
        project = existing_projects.get(slug)
        should_delete = False

        if not project:
            continue

        if mode == CleanupMode.NON_DRAFT:
            if project.get("status") != "draft":
                should_delete = True

        elif mode == CleanupMode.PUBLISHED:
            current_ver = data.get("version_version")
            if current_ver:
                try:
                    versions = api.get_project_versions(slug)
                    published_vers = [v["version_number"] for v in versions]
                    if current_ver in published_vers:
                        should_delete = True
                        logger.info(f"[{project_dir.name}] Version {current_ver} already published.")
                except ModrinthAPIError:
                    pass

        if should_delete:
            try:
                shutil.rmtree(project_dir)
                deleted_count += 1
                logger.info(f"[{project_dir.name}] Deleted.")
            except Exception as e:
                logger.error(f"Failed to delete {project_dir.name}: {e}")

    logger.info(f"Cleanup complete. Removed {deleted_count} directories.")


if __name__ == "__main__":
    app()