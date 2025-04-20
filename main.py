from ics import Calendar, Event
from arrow import Arrow
from typing import Set
import argparse
import os

# Go to https://mynypportal.nyp.edu.sg/en/dashboard/eserv-url/view-modules-registered.html to update this mapping
MODULE_NAME_MAPPING = {
    'IT1111': 'APPLIED MATHEMATICS IN COMPUTING',
    'IT1112': 'BUSINESS INNOVATION & ENTERPRISE',
    'IT1113': 'NETWORK TECHNOLOGIES',
    'IT1114': 'PROGRAMMING',
    'IT1115': 'UX DESIGN IN WEB DEVELOPMENT',
    'IT-DIT': 'DIT PERSONAL MENTOR CONTACT TIME'
}


parser = argparse.ArgumentParser(description='A script to reformat a valid NYP timetable from an .ics file so that it '
                                             'is easier to read in the calendar.')
parser.add_argument('input_file', help='The input .ics file')
parser.add_argument('output_file', help='The output formatted .ics file')
parser.add_argument('-o', '--overwrite-if-exists', dest='overwrite_if_exists', default=False, action='store_true',
                    help='Force overwrite output file if it already exists')
parser.add_argument('-v', '--verbose', dest="verbose", default=False, action='store_true',
                    help='Enable Verbose Printing')

args = parser.parse_args()


def get_event_by_time(calendar: Calendar, start: Arrow, end: Arrow) -> Event | None:
    for evnt in calendar.events:
        if evnt.begin == start and evnt.end == end:
            return evnt


def get_neighbouring_events_by_name(calendar: Calendar, name: str, start: Arrow, end: Arrow) -> Set[Event]:
    output = set()
    for evnt in calendar.events:
        if evnt.name == name and (evnt.begin == end.shift(minutes=10) or evnt.end == start.shift(minutes=-10)):
            output.add(evnt)
    return output


def merge_event_titles(title1: str, title2: str) -> str:
    title1_data = title1.split(' ')
    assert len(title1_data) == 3, f"Invalid Event Title For `title1`: {title1}"
    title1_course, title1_mode, title1_venue = title1_data
    title2_data = title2.split(' ')
    assert len(title2_data) == 3, f"Invalid Event Title For `title2`: {title2}"
    title2_course, title2_mode, title2_venue = title2_data
    course, mode, venue = title1_data
    if title1_course != title2_course:
        raise ValueError(f'Can\'t be in 2 courses {title1_course} and {title2_course} simultaneously')
        # course = f"{title1_course}/{title2_course}"
    if title1_mode != title2_mode:
        mode = f"{title1_mode}/{title2_mode}"
    if title1_venue != title2_venue:
        # raise ValueError(f'Can\'t be in 2 venues {title1_venue} and {title2_venue} simultaneously')
        venue = f"{title1_venue}/{title2_venue}"
    return f'{course} {mode} {venue}'


def merge_event_location(desc1: str, desc2: str) -> str:
    if desc1 == desc2:
        return desc2
    desc1_data = desc1.split(' ')
    desc2_data = desc2.split(' ')
    if len(desc1_data) != len(desc2_data):
        return desc1 + '\n' + desc2
    assert len(desc1_data) == 3, f"Invalid Event Location For `desc1`: {desc1}"
    assert len(desc2_data) == 3, f"Invalid Event Location For `desc2`: {desc2}"
    course, mode, classroom = desc1_data
    desc2_course, desc2_mode, desc2_classroom = desc2_data
    if course != desc2_course:
        course += f'/{desc2_course}'
    if mode != desc2_mode:
        mode += f'/{desc2_mode}'
    if classroom != desc2_classroom:
        classroom = f'({classroom[1:-1]}/{desc2_classroom[1:-1]})'
    return f"{course} {mode} {classroom}"


def is_same_event_location(desc1: str, desc2: str) -> bool:
    if desc1 == desc2:
        return True
    desc1_data = desc1.split(' ')
    desc2_data = desc2.split(' ')
    if len(desc1_data) != len(desc2_data):
        return False
    if len(desc1_data) != 3 or len(desc2_data) != 3:
        raise NotImplementedError(f"Unknown Event Location Handling.\n`desc1`: {desc1}\n`desc2`: {desc2}")
    desc1_course, desc1_mode, desc1_classroom = desc1_data
    desc2_course, desc2_mode, desc2_classroom = desc2_data
    if desc1_course != desc2_course or desc1_mode != desc2_mode:
        return False
    else:
        return True


def parse_event_title(title: str) -> str:
    new_title_data = title.split(' ')
    assert len(new_title_data) == 3, f"Invalid Event Title: {title}"
    course, mode, venue = new_title_data
    course = MODULE_NAME_MAPPING.get(course) or course
    if venue != 'ELEARNING':
        return f"({mode}) {course} [{venue}]"
    elif 'LEC' in mode:
        # noinspection SpellCheckingInspection
        return f"(ELEARN) {course}"
    else:
        # noinspection SpellCheckingInspection
        return f"(ELEARN) {course} [{mode}]"


def main():
    if args.verbose:
        print('Known Module Names:')
        for k, v in MODULE_NAME_MAPPING.items():
            print(f"  {k}: {v}")

    with open(args.input_file, 'r') as f:
        original_calendar = Calendar(f.read())
        new_calendar_with_merged = Calendar()
        new_calendar = Calendar()
        new_calendar_final = Calendar()
        f.close()
    print(f'Original no. of events: {len(original_calendar.events)}')

    # Stage 1: Add all calendar events, merging those next to each other
    for event in original_calendar.events:
        new_event = Event(name=event.name, begin=event.begin, end=event.end,
                          description=event.description, location=event.location)
        neighbouring_events = get_neighbouring_events_by_name(new_calendar_with_merged, event.name,
                                                              event.begin, event.end)
        if len(neighbouring_events) > 0:
            new_event.begin = min(event.begin, *[evnt.begin for evnt in neighbouring_events])
            new_event.end = max(event.end, *[evnt.end for evnt in neighbouring_events])
            for evnt in neighbouring_events:
                new_calendar_with_merged.events.remove(evnt)
        new_calendar_with_merged.events.add(new_event)
    print(f'No. of events after merging similar classes next to each other: {len(new_calendar_with_merged.events)}')

    # Stage 2: Add all calendar events again, removing duplicates (same course 2 teachers)
    for event in new_calendar_with_merged.events:
        new_event = Event(name=event.name, begin=event.begin, end=event.end,
                          description=event.description, location=event.location)
        duplicate_event_in_cal = get_event_by_time(new_calendar, event.begin, event.end)
        if duplicate_event_in_cal:
            new_event.name = merge_event_titles(new_event.name, duplicate_event_in_cal.name)
            new_event.description += f'\n{duplicate_event_in_cal.description}'
            # new_event.description = merge_event_desc(new_event.description,
            #                                          duplicate_event_in_cal.description)
            new_event.location = merge_event_location(new_event.location, duplicate_event_in_cal.location)
            new_calendar.events.remove(duplicate_event_in_cal)
        new_calendar.events.add(new_event)
    print(f'No. of events after merging classes with the same name: {len(new_calendar.events)}')

    # Stage 3: Make Event Name Easier to Read
    for event in new_calendar.events:
        new_event = event.clone()
        new_event.name = parse_event_title(new_event.name)
        new_calendar_final.events.add(new_event)

    # Stage 4: Show Timetable and Save
    if args.verbose:
        for event in new_calendar_final.events:
            print(event.name, end=': \n')
            print('  '+str(event.begin.format('DD/MM/YY (HH:mm)')), end=' - ')
            print(event.end.format('DD/MM/YY (HH:mm)'))
            for line in event.description.split('\n'):
                print(f'  {line}')
            for line in event.location.split('\n'):
                print(f'  {line}')
            print()

    with open(args.output_file, 'w') as f:
        f.writelines(new_calendar_final.serialize_iter())
        f.close()


if __name__ == '__main__':
    if not os.path.isfile(args.input_file):
        print(f"Input file '{args.input_file}' not found! Exiting...")
        exit(1)
    elif os.path.isfile(args.output_file) and not args.overwrite_if_exists:
        ans = ""
        while ans.lower() not in ['y', 'n', 'yes', 'no', 'maybe']:
            ans = input(f"Output file '{args.output_file}' already exists.\n  Would you like to overwrite it? (y/n): ")
        if ans.lower() in ['n', 'no', 'maybe']:
            print("User canceled operation. Exiting...")
            exit(0)
    main()
