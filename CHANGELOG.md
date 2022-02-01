# CHANGELOG

[AX] = "Admin experience" (Changes relevant mainly to admin users)  
[DX] = "Developer experience" (Changes relevant mainly to developers)

## 2022-02-01

### Changed

- Updated course_code_to_string template filter to format Banner courses

## 2022-01-28

### Added

- [AX] Added function to get Banner course info from SRS course code

## 2022-01-27

### Added

- Updated term values to support new "10/20/30" system, switching in March
- [AX] Added functions capable of distinguishing old from new systems in case admins still need to see old courses

## 2022-01-14

### Added

- [AX] Users are checked against student DW table if not found in employee
- Added placeholder to "User" input to show that it needs to be a pennkey

## 2022-01-12

### Added

- [DX] Request attempts are now logged with details of user, course requested,
  parameters. When request attempt fails, it logs the user, course, and error
  message for easier debugging and for finding errors even when user does not
  report them.

## 2022-01-11

### Added

- Open Data sync now adds instructors if they already have a User object in the CRF

### Fixed

- User's Home view only displays courses from the current or next terms

## 2022-01-10

### Changed

- Removed outdated message about course copy number

## 2022-01-06

### Fixed

- Courses now pull all related sections

## 2021-12-28

### Fixed

- "Copy from course" dropdown now excludes deleted Canvas courses

## 2021-12-27

### Fixed

- List of available courses to copy no longer includes deleted courses

## 2021-12-17

### Changed

- Wording for copy from content to make it clear that you can only select YOUR courses from dropdown

### Fixed

- Restore Instructor as option in additional enrollments

## 2021-12-08

### Fixed

- Additional enrollments in request form page

## 2021-12-07

### Changed

- No longer limit title overrides to 45 characters (increased to 255)

## 2021-12-06

### Changed

- Re-worded Multi-Section instructions to make it clear that sections will be grouped in the same site
- No longer display Multi-Section part of form if no sections are available

## 2021-12-01

### Fixed

- [AX] Create Canvas Sites failing when no sections are present

## 2021-11-30

### Fixed

- Auto-adds not enrolling

## 2021-11-29

### Fixed

- Error when data from Data Warehouse has null value for email

## 2021-11-17

### Added

- Pull courses from Open Data as well as DW in the daily sync

### Fixed

- [AX] Data Warehouse Lookup
- [DX] livereload (requires string instead of Path object for template dirs settings)

## 2021-11-16

### Added

- Daily sync for "current" and "next" terms, whose exact values are calculated by the current date

### Changed

- "Copy from existing site" dropdown lists highest Canvas ID number (most recent) first
- "Copy from existing site" searches anywhere in the course title instead of just the beginning of the title
- All autocomplete dropdowns no longer limit to 8 results when searching

### Fixed

- Paginator styles
- Filter function for Request list page
