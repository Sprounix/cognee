from datetime import datetime, date


def str2date(str_date, fmt='%Y-%m-%d'):
    s2d = datetime.strptime(str_date, fmt).date()
    return s2d


def calc_max_degree_graduate_date(educations, reverse=True):
    if not educations:
        return
    not_yet_graduated = [1 for edu in educations if edu.get("present") is True]
    if not_yet_graduated and len(not_yet_graduated) == 1:
        return datetime.now().date()
    end_times = [edu.get("end_date") for edu in educations if edu.get("end_date")]
    if not end_times:
        return
    last_end_time_str = sorted(end_times, reverse=reverse)[0]
    last_end_time = datetime.strptime(last_end_time_str, '%Y-%m-%d').date()
    return last_end_time


def calc_date_diff_days(work_end, work_start):
    days = (work_end - work_start).days
    if days <= 0:
        return 0
    return round(days / 365, 1)


def calc_resume_work_years(work_exps, graduated_date):
    try:
        if graduated_date:
            graduated_date = str2date(graduated_date)
            start_date_list = [
                w["start_date"] for w in work_exps
                if "start_date" in w and w["start_date"] and str2date(w["start_date"]) > graduated_date
            ]
        else:
            start_date_list = [w["start_date"] for w in work_exps if "start_date" in w and w["start_date"]]
        if not start_date_list:
            return 0
        first_start_date_str = sorted(start_date_list, reverse=False)[0]
        now = date.today()
        first_start_date = datetime.strptime(first_start_date_str, '%Y-%m-%d').date()
        years = calc_date_diff_days(now, first_start_date)
        return years
    except:
        return 0
