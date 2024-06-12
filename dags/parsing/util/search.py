import asyncio
import requests
from collections import deque

import aiohttp
from bs4 import BeautifulSoup
from parsing.util.data_structure import indstrict
from parsing.util.parser_util import url_addition
from parsing.util._typing import (
    UrlDataStructure,
    OuterData,
    ProcessUrlCollect,
    UrlCollect,
)


# DFS 함수 정의
def recursive_dfs(
    node: int, graph: UrlDataStructure, discovered: list = None
) -> list[int]:
    if discovered is None:
        discovered = []

    discovered.append(node)
    for n in graph.get(node, []):
        if n not in discovered:
            recursive_dfs(n, graph, discovered)

    return discovered


# BFS 함수 정의
def iterative_bfs(start_v: int, graph: dict[int, list[str]]) -> UrlCollect:
    start = deque()

    visited = set()
    queue = deque([start_v])
    visited.add(start_v)
    while queue:
        node: int = queue.popleft()
        if graph.get(node, []):
            start.append(graph[node])
            if node not in visited:
                visited.add(node)
                queue.append(node)

    return start


def deep_dive_search(page: ProcessUrlCollect, objection: str) -> UrlCollect:
    """
    Args:
        page (ProcessUrlCollect): 크롤링하려는 프로세스
        objection (str): 어떤 페이지에 할것인지

    Returns:
        UrlCollect: deque([URL 뭉치들]) [starting]
    """
    starting_queue = deque()
    tree: UrlDataStructure = indstrict(page)
    dfs: list[int] = recursive_dfs(1, tree)

    print(f"{objection}의 검색된 노드의 순서 --> {dfs}")
    for location in dfs:
        try:
            element: OuterData = tree[location]
            for num in element.keys():
                urls: list[str] = iterative_bfs(num, element).pop()
                starting_queue.append(urls)
        except (KeyError, IndexError):
            continue
    return starting_queue


class AsyncRequestAcquisitionHTML:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.url = url
        self.params = params
        self.headers = headers
        self.session = session

    async def async_source(
        self, response: aiohttp.ClientResponse, response_type: str
    ) -> str | dict:
        """비동기 방식으로 원격 자원에서 HTML 또는 JSON 데이터를 가져옴

        Args:
            response (aiohttp.ClientResponse) : session
            response_type (str): 가져올 데이터의 유형 ("html" 또는 "json")

        Returns:
            str | dict: HTML 또는 JSON 데이터
        """
        match response_type:
            case "html":
                return await response.text()
            case "json":
                return await response.json()

    async def async_request(
        self, response: aiohttp.ClientResponse
    ) -> str | dict[str, int] | dict[str, str]:
        """비동기 방식으로 원격 자원에 요청하고 상태 코드를 분류함

        Args:
            response (aiohttp.ClientResponse) : session

        Returns:
            str | dict[str, int | str]: 요청 결과 URL 또는 상태 코드
        """
        match response.status:
            case 200:
                return self.url
            case _:
                return {"status": response.status}

    async def async_type(
        self, type_: str, source: str = None
    ) -> str | dict | dict[str, int] | dict[str, str] | None:
        async with self.session.get(
            url=self.url, params=self.params, headers=self.headers
        ) as response:
            match type_:
                case "source":
                    return await self.async_source(response, source)
                case "request":
                    return await self.async_request(response)

    # fmt: off
    @staticmethod
    async def async_request_status(url: str) -> str | dict[str, int] | dict[str, str]:
        """주어진 URL에 대해 비동기 방식으로 요청하고 상태 코드를 반환함

        Args:
            url (str): 요청할 URL

        Returns:
            str | dict[str, int] | dict[str, str] : 요청 결과 URL 또는 상태 코드
        """
        async with aiohttp.ClientSession() as session:
            return await AsyncRequestAcquisitionHTML(session, url).async_type(type_="request")

    @staticmethod
    async def async_fetch_content(
        response_type: str,
        url: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str | dict:
        """비동기 방식으로 원격 자원에서 HTML 또는 JSON 데이터를 가져옴

        Args:
            response_type (str): 가져올 데이터의 유형 ("html" 또는 "json")
            url (str): 가져올 데이터의 URL
            params (dict[str, str] | None, optional): 요청 시 사용할 파라미터
            headers (dict[str, str] | None, optional): 요청 시 사용할 헤더

        Returns:
            str | dict: HTML 또는 JSON 데이터
        """
        async with aiohttp.ClientSession() as session:
            return await AsyncRequestAcquisitionHTML(
                    session, url, params, headers
                ).async_type(type_="source", source=response_type)


class AsyncWebCrawler:
    def __init__(self, start_url: str, max_pages: int, max_depth: int) -> None:
        self.start_url = start_url
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.visited_urls = set()
        self.url_queue = asyncio.Queue()
        self.url_queue.put_nowait((start_url, 0))  # Put start URL with depth 0
        self.results = {}

    def parse_links(self, content: str, base_url: str) -> set[str]:
        soup = BeautifulSoup(content, "lxml")
        links = set()
        for a_tag in soup.find_all("a", href=True):
            link: str = a_tag["href"]
            if link.startswith("/"):
                link = url_addition(base_url, link)
            if link.startswith("http"):
                links.add(link)
        return links

    async def crawl(self) -> None:
        while not self.url_queue.empty() and len(self.visited_urls) < self.max_pages:
            current_url, depth = await self.url_queue.get()

            if current_url in self.visited_urls or depth > self.max_depth:
                continue

            self.visited_urls.add(current_url)
            content = await AsyncRequestAcquisitionHTML.async_fetch_content(
                "html", current_url
            )

            if content:
                if depth < self.max_depth:
                    new_links = self.parse_links(content, current_url)
                    self.results[current_url] = new_links
                    for link in new_links:
                        if link not in self.visited_urls:
                            await self.url_queue.put((link, depth + 1))

    async def run(self, num_tasks: int = 4) -> dict[str, set[str]]:
        tasks = [asyncio.create_task(self.crawl()) for _ in range(num_tasks)]
        await asyncio.gather(*tasks)
        return self.results
