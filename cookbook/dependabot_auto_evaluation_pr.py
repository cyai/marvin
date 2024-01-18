import os
from typing import List

from github import Github
from marvin import ai_fn
from openai import OpenAI


def authenticate_github(username: str, token: str) -> Github:
    return Github(username, token)


def get_dependabot_prs(repo) -> List:
    return repo.get_pulls(state="open", head="dependabot")


def heruistics(pr) -> float:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def evaluate_heuristic(pr, labels, description, files_changed) -> float:
        """
        Analyzes the PR labels, description, and files changed to calculate a confidence score using sentiment analysis.

        Args:
            pr: The pull request object.
            labels: The labels attached to the pull request.
            description: The description of the pull request.
            files_changed: The files changed in the pull request.

        Returns:
            confidence_score: The calculated confidence score.
        """

    ai_fn(evaluate_heuristic, client=client)(
        pr, labels=pr.labels, description=pr.description, files_changed=pr.files_changed
    )


def merge_pr(pr) -> None:
    pr.merge()


def notify_maintainer_merger(pr, confidence_score: float) -> None:
    pr.create_issue_comment(
        f"Hey @@zzstoatzz! I have evaluated this PR and am {confidence_score*100}%"
        " confident that it is safe to merge. I have gone ahead and merged it for you."
    )


def notify_maintainer(pr, confidence_score: float) -> None:
    pr.create_issue_comment(
        f"Hey @@zzstoatzz! I have evaluated this PR and am {confidence_score*100}%"
        " confident that it is safe to merge. Could you please take a look. Thanks!"
    )


def close_pr(pr) -> None:
    pr.close()


def main() -> None:
    github_username = os.getenv("GITHUB_USERNAME")
    github_token = os.getenv("GITHUB_TOKEN")

    if not github_username or not github_token:
        raise ValueError("Both GITHUB_USERNAME and GITHUB_TOKEN must be set")

    g = authenticate_github(github_username, github_token)
    repo = g.get_repo("refectHQ/marvin")

    prs = get_dependabot_prs(repo)

    for pr in prs:
        confidence_score = heruistics(pr)

        if confidence_score > 0.8:
            merge_pr(pr)
            notify_maintainer_merger(pr)
        elif confidence_score > 0.5:
            notify_maintainer(pr)
        else:
            close_pr(pr)


if __name__ == "__main__":
    main()