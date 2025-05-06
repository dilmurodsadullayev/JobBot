import aiohttp
import json
import logging
import math 

DEFAULT_ITEMS_PER_PAGE = 10 

class VacancyParser:
    def __init__(self, api_url):
        self.api_url = api_url
        self._session: aiohttp.ClientSession | None = None
        logging.info(f"VacancyParser created for URL: {api_url}")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Creates or returns the existing aiohttp ClientSession."""
        if self._session is None or self._session.closed:
            logging.info("Creating new aiohttp ClientSession.")
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Closes the aiohttp ClientSession if it exists."""
        if self._session and not self._session.closed:
            logging.info("Closing aiohttp ClientSession.")
            await self._session.close()
            self._session = None 

    async def get_vacancies(self, query: str = "", page: int = 1) -> tuple[list | None, int, int]:
        
        session = await self._get_session()
        params = {'page': str(page)} 
        if query:
             params['query'] = query

        try:
            logging.info(f"Requesting vacancies from {self.api_url} with params: {params}")
            async with session.get(self.api_url, params=params) as response:
                logging.info(f"API response status: {response.status}")
                if response.status == 200:
                    try:
                        data = await response.json() 
                        logging.debug(f"API raw response data (page {page}): {data}")

                        vacancies = None
                        total_items = 0
                        total_pages = 0

                        if isinstance(data, dict) and 'results' in data and isinstance(data['results'], list) and 'count' in data:
                             vacancies = data['results']
                             try:
                                 total_items = int(data.get('count', 0))
                             except (ValueError, TypeError):
                                 logging.warning(f"Could not parse 'count' field ({data.get('count')}) as integer.")
                                 total_items = 0 

                             items_on_this_page = len(vacancies)
                             items_per_page = items_on_this_page if items_on_this_page > 0 and page == 1 else DEFAULT_ITEMS_PER_PAGE # Simple heuristic
                             if total_items > 0 and items_per_page > 0:
                                 total_pages = math.ceil(total_items / items_per_page)
                             elif total_items == 0:
                                 total_pages = 0 
                             else: 
                                 total_pages = 1 

                             logging.info(f"Parsed {len(vacancies)} vacancies. Total items: {total_items}, Calculated pages: {total_pages} (assuming ~{items_per_page}/page).")
                             return vacancies, total_pages, total_items

                        elif isinstance(data, list):
                             vacancies = data
                             total_items = len(vacancies) 
                             total_pages = 1 
                             logging.warning("API returned a list directly. Pagination may not work correctly or show total counts.")
                             return vacancies, total_pages, total_items
                        else:
                             logging.warning(f"API returned unknown JSON structure: {type(data)}")
                             return None, 0, 0

                    except (aiohttp.ContentTypeError, json.JSONDecodeError) as e:
                        logging.error(f"Failed to decode API response as JSON: {e}", exc_info=True)
                        try:
                            text_data = await response.text()
                            logging.debug(f"Non-JSON Response text: {text_data[:200]}...")
                        except Exception as text_err:
                            logging.error(f"Could not even read response text after JSON error: {text_err}")
                        return None, 0, 0
                else:
                    error_text = await response.text()
                    logging.error(f"API request failed with status: {response.status}, Response: {error_text[:500]}") # Log part of error response
                    return None, 0, 0 
        except aiohttp.ClientError as e:
            logging.error(f"Network or connection error during API request: {e}", exc_info=True)
            return None, 0, 0 
        except Exception as e:
            logging.error(f"An unexpected error occurred in get_vacancies: {e}", exc_info=True)
            return None, 0, 0