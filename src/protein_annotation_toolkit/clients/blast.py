"""
NCBI BLAST API client.

Submits BLAST searches and retrieves results from NCBI.
"""

import asyncio
import re
from typing import Optional

import structlog

from protein_annotation_toolkit.clients.base import BaseAPIClient
from protein_annotation_toolkit.config import get_settings
from protein_annotation_toolkit.exceptions import APIError

# Set up logger
logger = structlog.get_logger(__name__)


class BlastClient(BaseAPIClient):
    """
    Client for NCBI BLAST API.

    Provides methods to:
    - Submit BLAST searches
    - Poll for completion
    - Retrieve XML results
    """

    def __init__(self):
        """
        Initialize BLAST client.

        Uses base URL from application settings.
        """
        settings = get_settings()
        super().__init__(base_url=settings.blast_api_base)

    async def submit_search(
        self,
        sequence: str,
        program: str = "blastp",
        database: str = "nr",
        email: Optional[str] = None
    ) -> str:
        """
        Submit a BLAST search.

        Args:
            sequence: Query sequence (FASTA format or plain sequence)
            program: BLAST program (blastp, blastn, blastx, tblastn, tblastx)
            database: Target database (nr, swissprot, pdb, etc.)
            email: Email address (required by NCBI for courtesy)

        Returns:
            Request ID (RID) for tracking the search

        Raises:
            APIError: If submission fails

        Example:
            >>> async with BlastClient() as client:
            ...     rid = await client.submit_search(
            ...         sequence="MGLLDGNPA...",
            ...         program="blastp",
            ...         database="nr",
            ...         email="user@example.com"
            ...     )
            ...     print(f"Submitted search: {rid}")
        """
        # Get email from settings if not provided
        if not email:
            settings = get_settings()
            email = settings.ncbi_email
            if not email:
                logger.warning("no_email_provided", message="Consider setting NCBI_EMAIL")

        # Prepare request parameters
        params = {
            "CMD": "Put",
            "PROGRAM": program,
            "DATABASE": database,
            "QUERY": sequence,
        }

        # Add email if available
        if email:
            params["EMAIL"] = email

        logger.info(
            "submitting_blast",
            program=program,
            database=database,
            sequence_length=len(sequence)
        )

        try:
            # Submit via POST
            response = await self.post(
                "",  # Base URL is the BLAST.cgi endpoint
                data=params
            )

            # Extract RID from response
            # Format: "    RID = XXXXXXXX"
            rid_match = re.search(r'RID\s*=\s*(\S+)', response)
            if not rid_match:
                raise APIError("Failed to extract RID from BLAST response")

            rid = rid_match.group(1)

            # Extract RTOE (estimated time to completion)
            rtoe_match = re.search(r'RTOE\s*=\s*(\d+)', response)
            rtoe = int(rtoe_match.group(1)) if rtoe_match else 60

            logger.info(
                "blast_submitted",
                rid=rid,
                rtoe=rtoe,
                program=program,
                database=database
            )

            return rid

        except Exception as e:
            logger.error("blast_submission_failed", error=str(e))
            raise APIError(f"Failed to submit BLAST search: {e}")

    async def check_status(self, rid: str) -> str:
        """
        Check the status of a BLAST search.

        Args:
            rid: Request ID from submit_search

        Returns:
            Status string: "WAITING", "READY", "FAILED", or "UNKNOWN"

        Raises:
            APIError: If status check fails

        Example:
            >>> status = await client.check_status(rid)
            >>> if status == "READY":
            ...     results = await client.get_results(rid)
        """
        # Prepare request parameters
        params = {
            "CMD": "Get",
            "FORMAT_OBJECT": "SearchInfo",
            "RID": rid,
        }

        logger.debug("checking_blast_status", rid=rid)

        try:
            # Fetch status
            response = await self.get("", params=params)

            # Parse status from response
            if "Status=WAITING" in response:
                status = "WAITING"
            elif "Status=READY" in response:
                # Check if there are hits
                if "ThereAreHits=yes" in response:
                    status = "READY"
                else:
                    status = "NO_HITS"
            elif "Status=FAILED" in response:
                status = "FAILED"
            elif "Status=UNKNOWN" in response:
                status = "UNKNOWN"
            else:
                status = "UNKNOWN"

            logger.debug("blast_status_checked", rid=rid, status=status)

            return status

        except Exception as e:
            logger.error("status_check_failed", rid=rid, error=str(e))
            raise APIError(f"Failed to check BLAST status: {e}")

    async def poll_until_ready(
        self,
        rid: str,
        poll_interval: int = 5,
        max_wait: int = 600
    ) -> bool:
        """
        Poll BLAST search until complete or timeout.

        Args:
            rid: Request ID
            poll_interval: Seconds between polls
            max_wait: Maximum seconds to wait

        Returns:
            True if ready, False if timeout or failed

        Example:
            >>> if await client.poll_until_ready(rid):
            ...     results = await client.get_results(rid)
        """
        logger.info("polling_blast", rid=rid, max_wait=max_wait)

        elapsed = 0

        while elapsed < max_wait:
            # Check status
            status = await self.check_status(rid)

            if status == "READY":
                logger.info("blast_ready", rid=rid, elapsed=elapsed)
                return True

            elif status in ["FAILED", "NO_HITS"]:
                logger.warning("blast_not_ready", rid=rid, status=status)
                return False

            elif status == "UNKNOWN":
                logger.warning("blast_expired", rid=rid)
                return False

            # Status is WAITING - continue polling
            logger.debug("blast_waiting", rid=rid, elapsed=elapsed)

            # Wait before next poll
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        # Timeout
        logger.warning("blast_timeout", rid=rid, elapsed=elapsed)
        return False

    async def get_results(self, rid: str, format_type: str = "XML") -> str:
        """
        Retrieve BLAST results.

        Args:
            rid: Request ID
            format_type: Output format (XML, Text, HTML, etc.)

        Returns:
            BLAST results in requested format

        Raises:
            APIError: If retrieval fails

        Example:
            >>> async with BlastClient() as client:
            ...     xml = await client.get_results(rid, format_type="XML")
        """
        # Prepare request parameters
        params = {
            "CMD": "Get",
            "FORMAT_TYPE": format_type,
            "RID": rid,
        }

        logger.info("retrieving_blast_results", rid=rid, format=format_type)

        try:
            # Fetch results
            response = await self.get("", params=params)

            # Validate XML if format is XML
            if format_type == "XML" and not response.strip().startswith("<?xml"):
                raise APIError(f"Invalid XML response for RID {rid}")

            logger.info(
                "blast_results_retrieved",
                rid=rid,
                size=len(response)
            )

            return response

        except Exception as e:
            logger.error("results_retrieval_failed", rid=rid, error=str(e))
            raise APIError(f"Failed to retrieve BLAST results: {e}")

    async def submit_and_wait(
        self,
        sequence: str,
        program: str = "blastp",
        database: str = "nr",
        email: Optional[str] = None,
        poll_interval: int = 5,
        max_wait: int = 600
    ) -> Optional[str]:
        """
        Convenience method: submit search, wait for completion, and return XML results.

        Args:
            sequence: Query sequence
            program: BLAST program
            database: Target database
            email: Email address
            poll_interval: Seconds between status checks
            max_wait: Maximum seconds to wait

        Returns:
            XML results if successful, None if failed or timeout

        Example:
            >>> async with BlastClient() as client:
            ...     xml = await client.submit_and_wait(
            ...         sequence="MGLLDGNPA...",
            ...         program="blastp",
            ...         database="nr"
            ...     )
            ...     if xml:
            ...         # Parse and process results
            ...         pass
        """
        logger.info(
            "blast_workflow_start",
            program=program,
            database=database
        )

        # Step 1: Submit search
        rid = await self.submit_search(
            sequence=sequence,
            program=program,
            database=database,
            email=email
        )

        # Step 2: Wait for completion
        ready = await self.poll_until_ready(
            rid=rid,
            poll_interval=poll_interval,
            max_wait=max_wait
        )

        if not ready:
            logger.warning("blast_workflow_failed", rid=rid)
            return None

        # Step 3: Retrieve results
        xml = await self.get_results(rid, format_type="XML")

        logger.info("blast_workflow_complete", rid=rid)

        return xml
