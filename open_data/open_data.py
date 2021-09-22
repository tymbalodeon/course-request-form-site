import requests


class OpenData(object):
    def __init__(self, base_url, id, key):
        self.headers = {"Authorization-Bearer": id, "Authorization-Token": key}
        self.base_url = base_url
        self.uri = ""
        self.params = {
            "number_of_results_per_page": 30,
            "page_number": 1,
        }

    def clear_settings(self):
        self.uri = ""
        self.params = {
            "number_of_results_per_page": 30,
            "page_number": 1,
        }

    def set_uri(self, new_uri):
        self.uri = new_uri

    def add_param(self, key, value):
        self.params[key] = value

    def next_page(self):
        current = self.params["page_number"]
        self.add_param("page_number", current + 1)
        result_data, service_meta = self.call_api(only_data=False)

        if service_meta["current_page_number"] == current + 1:
            return result_data
        else:
            return None

    def call_api(self, only_data=True):
        url = f"{self.base_url}{self.uri}"
        response = requests.get(url, headers=self.headers, params=self.params)
        response_json = response.json()
        service_meta = response_json["service_meta"]

        if "error_text" in service_meta and service_meta["error_text"]:
            print(service_meta["error_text"])
            return "ERROR"
        elif service_meta["current_page_number"] < self.params["page_number"]:
            return response_json["result_data"], service_meta
        elif service_meta["results_per_page"] == len(response_json["result_data"]):
            result_data = response_json["result_data"]
        elif isinstance(response_json["result_data"], list):
            result_data = (
                response_json["result_data"][0]
                if response_json["result_data"]
                else response_json["result_data"]
            )
        else:
            result_data = response_json["result_data"]

        if only_data:
            return result_data
        else:
            return result_data, response_json["service_meta"]

    def get_available_terms(self):
        url = f"{self.base_url}course_section_search_parameters/"
        response = requests.get(url, headers=self.headers).json()

        return [*response["result_data"][0]["available_terms_map"]]

    def get_courses_by_term(self, term):
        self.clear_settings()
        self.set_uri("course_section_search")
        self.add_param("term", term)

        return self.call_api(only_data=True)

    def find_school_by_subj(self, subject):
        url = f"{self.base_url}course_info/{subject}/"
        params = {"results_per_page": 2}
        response = requests.get(url, headers=self.headers, params=params).json()

        return response["result_data"][0]["school_code"]

    def get_available_activity(self):
        url = f"{self.base_url}course_section_search_parameters/"
        response = requests.get(url, headers=self.headers).json()

        return response["result_data"][0]["activity_map"]

    def get_available_subj(self):
        url = f"{self.base_url}course_section_search_parameters/"
        response = requests.get(url, headers=self.headers).json()

        try:
            result = (
                response["service_meta"]["error_text"]
                if response["service_meta"]["error_text"]
                else response["result_data"][0]["departments_map"]
            )
        except Exception as error:
            result = error

        return result
