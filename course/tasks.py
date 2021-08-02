from __future__ import absolute_import, unicode_literals

import time
from datetime import datetime
from logging import getLogger

from canvasapi.tab import Tab
from celery import task

from canvas.api import (
    find_account,
    find_term_id,
    get_canvas,
    get_user_by_sis,
    mycreate_user,
)
from course import utils
from course.models import CanvasSite, Course, Request, User
from course.serializers import RequestSerializer
from datawarehouse import datawarehouse


@task()
def task_nightly_sync(term):
    time_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    f = open("course/static/log/night_sync.log", "a")
    datawarehouse.daily_sync(term)
    time_end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    f.write("Nighly Update " + term + ":" + time_start + " - " + time_end + "\n")
    f.close()


@task()
def task_test():
    time_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    f = open("course/static/log/test.log", "a")
    f.write(time_start + "\n")
    f.close()


@task()
def task_pull_courses(term):
    datawarehouse.pull_courses(term)


def update_instrutors(term):
    chain = task_clear_instructors.s(term) | task_pull_instructors.s(term)
    chain()


@task()
def task_clear_instructors(term):
    datawarehouse.clear_instructors(term)  # -- only for non requested courses


@task()
def task_pull_instructors(term):
    datawarehouse.pull_instructors(term)  # -- only for non requested courses


@task()
def task_process_canvas():
    utils.process_canvas()


@task()
def task_update_sites_info(term):
    print("term", term)
    utils.update_sites_info(
        term
    )  # info # -- for each Canvas Site in the CRF check if its been altered
    print("finished canvas site metadata update")


@task()
def task_delete_canceled_courses(term):
    datawarehouse.delete_canceled_courses(term)


# ----------- CHECK COURSE IN CANVAS ---------------
# FREQUENCY = NIGHTLY
@task()
def task_check_courses_in_canvas():
    """
    check to see if any of the courses that do not have a request object
    associated with them exist yet in Canvas if they do then write to the file
    and set the course to request_override
    """
    # courses = Course.objects.filter(requested=False).filter(requested_override=False)
    # for course in courses:
    #     # if the section doesnt exist then it will return None
    #     found = find_in_canvas("SRS_" + course.srs_format())
    #     # found == None if there is NO CANVAS SECTION
    #     if found is None:
    #         pass  # this course doesnt exist in canvas yet
    #     else:
    #         # set the course to requested
    #         # course.requested_override = True
    #         # check that the canvas site exists in the CRF
    #         try:
    #             canvas_site = CanvasSite.objects.get(canvas_id=found.course_id)

    #         except Exception:  # doesnt exist in CRF
    #             # Create in CRF
    #             canvas_site = CanvasSite
    #             pass


# ----------- REMOVE CANCELED REQUESTS ---------------
@task()
def delete_canceled_requests():
    _to_process = Request.objects.filter(status="CANCELED")
    for request in _to_process:
        request.delete()


# ----------- CREATE COURSE IN CANVAS ---------------
# FREQUENCY = NIGHTLY
# https://github.com/upenn-libraries/accountservices/blob/master/siterequest/management/commands/process_approved_items.py


# CREATE LOGIN -- USERNAME: PENNKEY, SIS ID: PENN_ID, fullname
@task()
def check_for_account(pennkey):
    user = get_user_by_sis(pennkey)
    if user is None:
        try:
            crf_account = User.objects.get(username=pennkey)
            pennid = crf_account.profile.pennid
            full_name = crf_account.get_full_name()
            canvas_account = mycreate_user(pennkey, pennid, full_name)
            if canvas_account:
                return canvas_account
            else:
                return None
        except Exception:
            pass


def add_request_process_notes(message, request):
    start = ", " if request.process_notes else ""
    request.process_notes += f"{start}{message}"
    request.save()


@task()
def create_canvas_sites(
    requested_courses=Request.objects.filter(status="APPROVED"),
    sections=None,
    test=False,
    verbose=True,
):
    if verbose:
        print(") Creating Canvas sites for requested courses...")

    if not requested_courses:
        if verbose:
            print("SUMMARY")
            print("- No requested courses found.")
            print("FINISHED")

        return

    section_already_exists = False

    for request in requested_courses:
        request.status = "IN_PROCESS"
        request.save()
        serialized = RequestSerializer(request)
        additional_sections = []
        course_requested = request.course_requested

        if verbose:
            print(f") Creating Canvas site for {course_requested}...")

        account = find_account(
            course_requested.course_schools.canvas_subaccount, test=test
        )

        if account:
            if (
                course_requested.course_primary_subject.abbreviation
                != course_requested.course_subject.abbreviation
            ):
                if course_requested.primary_crosslist:
                    section_name_code = course_requested.srs_format_primary()
                else:
                    add_request_process_notes("Primary crosslist not set", request)

                    continue
            else:
                section_name_code = (
                    f"{course_requested.course_subject.abbreviation}"
                    f" {course_requested.course_number}-"
                    f"{course_requested.course_section}"
                    f" {course_requested.year}{course_requested.course_term}"
                )

            if request.title_override:
                name = f"{section_name_code} {request.title_override[:45]}"
                section_name = f"{section_name_code}{request.title_override[:45]}"
            else:
                name = f"{section_name_code} {course_requested.course_name}"
                section_name = f"{section_name_code} {course_requested.course_name}"

            sis_course_id = f"SRS_{course_requested.srs_format_primary()}"
            term_id = find_term_id(
                96678,
                f"{course_requested.year}{course_requested.course_term}",
                test=test,
            )
            course = {
                "name": name,
                "sis_course_id": sis_course_id,
                "course_code": sis_course_id,
                "term_id": term_id,
            }

            already_exists = False

            try:
                canvas_course = account.create_course(course=course)
            except Exception:
                try:
                    canvas_course = get_canvas(test).get_course(
                        sis_course_id, use_sis_id=True
                    )
                    canvas_course.update(course=course)
                    already_exists = True
                except Exception as error:
                    add_request_process_notes(
                        "course site creation failed--check if it already exists",
                        request,
                    )

                    message = f"\t- ERROR: failed to create site ({error})"
                    getLogger("error_logger").error(message)

                    if verbose:
                        print(message)

                    continue

            try:
                canvas_course.update(course={"storage_quota_mb": 2000})
            except Exception:
                add_request_process_notes("course site quota not raised", request)

            if not already_exists:
                try:
                    additional_section = {"course_section": "", "instructors": ""}
                    additional_section[
                        "course_section"
                    ] = canvas_course.create_course_section(
                        course_section={
                            "name": section_name,
                            "sis_section_id": sis_course_id,
                        },
                        enable_sis_reactivation=True,
                    )
                    MAIN_SECTION = additional_section["course_section"]
                    additional_section[
                        "instructors"
                    ] = course_requested.instructors.all()
                    additional_sections += [additional_section]
                except Exception as error:
                    add_request_process_notes("failed to create main section", request)

                    message = f"\t- ERROR: failed to create main section ({error})"
                    getLogger("error_logger").error(message)

                    if verbose:
                        print(message)

                    section_already_exists = True

                    continue
        else:
            add_request_process_notes("failed to locate Canvas Account", request)

            message = "\t- ERROR: failed to locate Canvas Account"
            getLogger("error_logger").error(message)

            if verbose:
                print(message)

            continue

        if request.title_override:
            namebit = request.title_override
        else:
            namebit = course_requested.course_name

        if sections:
            try:
                serialized.data["additonal_sections"] = serialized.data[
                    "additional_sections"
                ].extend(sections)
            except Exception:
                serialized.data["additional_sections"] = sections

        for section in serialized.data["additional_sections"]:
            try:
                section_course = Course.objects.get(course_code=section)

                if section_course.course_activity.abbr != "LEC":
                    namebit = section_course.course_activity.abbr

                sis_section = f"SRS_{section_course.srs_format_primary()}"
                additional_section = {"course_section": "", "instructors": ""}
                additional_section[
                    "course_section"
                ] = canvas_course.create_course_section(
                    course_section={
                        "name": section_course.srs_format_primary(sis_id=False)
                        + " "
                        + namebit,
                        "sis_section_id": sis_section,
                    },
                    enable_sis_reactivation=True,
                )
                additional_section["instructors"] = section_course.instructors.all()
                additional_sections += [additional_section]
            except Exception as error:
                add_request_process_notes("failed to create section", request)

                message = f"\t- ERROR: failed to create section ({error})"
                getLogger("error_logger").error(message)

                if verbose:
                    print(message)

                continue

        enrollment_types = {
            "INST": "TeacherEnrollment",
            "instructor": "TeacherEnrollment",
            "TA": "TaEnrollment",
            "ta": "TaEnrollment",
            "DES": "DesignerEnrollment",
            "designer": "DesignerEnrollment",
            "LIB": "DesignerEnrollment",
            "librarian": "DesignerEnrollment",
        }
        librarian_role_id = "1383"

        for section in additional_sections:
            for instructor in section["instructors"]:
                user = get_user_by_sis(instructor.username, test=test)

                if user is None:
                    try:
                        user = mycreate_user(
                            instructor.username,
                            instructor.profile.penn_id,
                            instructor.email,
                            f"{instructor.first_name} {instructor.last_name}",
                            test=test,
                        )
                        add_request_process_notes(
                            f"created account for user: {instructor.username}", request
                        )
                    except Exception:
                        add_request_process_notes(
                            f"failed to create account for user: {instructor.username}",
                            request,
                        )

                try:
                    canvas_course.enroll_user(
                        user.id,
                        "TeacherEnrollment",
                        enrollment={
                            "enrollment_state": "active",
                            "course_section_id": section["course_section"].id,
                        },
                    )
                except Exception:
                    add_request_process_notes(
                        f"failed to add user: {instructor.username}", request
                    )
        additional_enrollments = serialized.data["additional_enrollments"]

        for enrollment in additional_enrollments:
            user = enrollment["user"]
            role = enrollment["role"]
            user_canvas = get_user_by_sis(user)

            if user_canvas is None:
                try:
                    user_crf = User.objects.get(username=user)
                    user_canvas = mycreate_user(
                        user,
                        user_crf.profile.penn_id,
                        user_crf.email,
                        user_crf.first_name + user_crf.last_name,
                    )
                    add_request_process_notes(
                        f"created account for user: {instructor.username}", request
                    )
                except Exception:
                    add_request_process_notes(
                        f"failed to create account for user: {instructor.username}",
                        request,
                    )

            if role == "LIB" or role == "librarian":
                try:
                    canvas_course.enroll_user(
                        user_canvas.id,
                        enrollment_types[role],
                        enrollment={
                            "course_section_id": MAIN_SECTION.id,
                            "role_id": librarian_role_id,
                            "enrollment_state": "active",
                        },
                    )
                except Exception:
                    add_request_process_notes(f"failed to add user: {user}", request)
            else:
                try:
                    canvas_course.enroll_user(
                        user_canvas.id,
                        enrollment_types[role],
                        enrollment={
                            "course_section_id": MAIN_SECTION.id,
                            "enrollment_state": "active",
                        },
                    )
                except Exception:
                    add_request_process_notes(f"failed to add user: {user}", request)

        if serialized.data["reserves"]:
            try:
                tab = Tab(
                    canvas_course._requester,
                    {
                        "course_id": canvas_course.id,
                        "id": "context_external_tool_139969",
                        "label": "Course Materials @ Penn Libraries",
                    },
                )
                tab.update(hidden=False)

                if tab.visibility != "public":
                    add_request_process_notes("failed to configure ARES", request)
            except Exception as error:
                message = f"\t- ERROR: {error}"
                getLogger("error_logger").error(message)

                if verbose:
                    print(message)

                add_request_process_notes("failed to try to configure ARES", request)

        if serialized.data["copy_from_course"]:
            try:
                if verbose:
                    print(
                        "\t* Copying course data from course id"
                        f" {serialized.data['copy_from_course']}..."
                    )

                source_course_id = serialized.data["copy_from_course"]
                content_migration = canvas_course.create_content_migration(
                    migration_type="course_copy_importer",
                    settings={"source_course_id": source_course_id},
                )

                while (
                    content_migration.get_progress == "queued"
                    or content_migration.get_progress == "running"
                ):
                    if verbose:
                        print("\t* Migration running...")

                    time.sleep(8)

                if verbose:
                    print("\t- MIGRATION COMPLETE")
                    print("\t* Deleting Zoom events...")

                canvas = get_canvas(test)
                course_string = f"course_{canvas_course.id}"
                events = canvas.get_calendar_events(
                    context_codes=[course_string], all_events=True
                )
                zoom_events = list()

                for event in events:
                    if (
                        (event.location_name and "zoom" in event.location_name.lower())
                        or (event.description and "zoom" in event.description.lower())
                        or (event.title and "zoom" in event.title.lower())
                    ):
                        zoom_events.append(event.id)

                for event_id in zoom_events:
                    event = canvas.get_calendar_event(event_id)
                    deleted = event.delete(
                        cancel_reason=(
                            "Zoom event was copied from a previous term and no longer"
                            " relevant"
                        )
                    )
                    if verbose:
                        print(f"\t- Event '{deleted}' deleted.")

            except Exception as error:
                message = f"\t- ERROR: {error}"
                getLogger("error_logger").error(message)

                if verbose:
                    print(message)

        instructors = canvas_course.get_enrollments(type="TeacherEnrollment")._elements
        canvas_id = canvas_course.id
        request_instance = request
        name = canvas_course.name
        sis_course_id = canvas_course.sis_course_id
        workflow_state = canvas_course.workflow_state
        site = CanvasSite.objects.update_or_create(
            canvas_id=canvas_id,
            defaults={
                "request_instance": request_instance,
                "name": name,
                "sis_course_id": sis_course_id,
                "workflow_state": workflow_state,
            },
        )[0]
        request.canvas_instance = site

        for instructor in instructors:
            try:
                user = User.objects.get(username=instructor)
                site.owners.add(user)
            except Exception:
                pass

        request.status = "COMPLETED"
        request.save()

        if verbose:
            print(f"- Canvas site successfully created: {site}.")

    if verbose:
        print("FINISHED")

    if section_already_exists:
        return "section already exists"
