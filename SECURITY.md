# Security policy

## Supported use

`durable-web-monitor-mcp` is intended for monitoring public HTTPS pages that you are authorized to access.

Do not point it at private admin interfaces, local services, cloud metadata endpoints, credential-bearing URLs, or systems you are not authorized to query.

## Network boundary

The application performs defensive URL validation:

- HTTPS only;
- no embedded username/password;
- DNS resolution before fetch;
- rejection of loopback, private, link-local, multicast, reserved and unspecified addresses;
- redirect revalidation in the direct adapter;
- bounded response size and redirect count.

These checks are **defense in depth, not a complete SSRF sandbox**. DNS can change between validation and connection, and a browser can make secondary requests that are not visible to this application's URL validator.

For hostile or user-controlled URLs, deploy the monitor inside a network sandbox with restrictive outbound rules. Deny access to RFC1918/private ranges, localhost, link-local ranges, cloud metadata services and other sensitive internal networks at the infrastructure layer.

## Browser isolation

The browser adapter launches a fresh Playwright MCP process with `--isolated` and closes it after each fetch. This prevents normal browser profile persistence between checks.

Playwright MCP explicitly documents that it is not a security boundary. Treat browser isolation as state hygiene, not network isolation.

## Secrets

This project does not need website credentials for its intended public-page use case. Do not put secrets in monitor names, URLs, watch terms, logs, Git history or SQLite notification text.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting feature for this repository if enabled. Otherwise contact the repository owner privately rather than opening a public issue with exploit details.
