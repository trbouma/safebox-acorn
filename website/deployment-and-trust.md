---
title: Deployment and Trust
description: The ways Acorn can run, who supplies its execution environment, and what must be trusted in each deployment.
---

# Deployment and trust

Acorn is an installable component rather than a single hosted product. It can
run locally, inside an application, through a trusted provider, in an isolated
FreeBSD jail, or eventually with keys protected by dedicated hardware.

Every deployment has a trust boundary. User control does not come from hiding
that boundary; it comes from making it explicit and preserving continuity when
the surrounding operator or infrastructure changes.

This page primarily describes **operational reliance**: which systems and
operators must behave correctly. That is distinct from trust in an actor. In
the actor-centred sense, trust is a counterparty's willingness to rely on the
belief that a key and its signed history remain under the intentional control
of a person or accountable organization over time. A relay or operator may be
an essential dependency without being the actor represented by the key.

## The roles are separate

```text
keys  -> continuity, signing, decryption, and authorization
code  -> the execution environment and trusted operator
data  -> signed and encrypted state hosted on relays
mint  -> ecash issuance and spend-state authority
app   -> experience, workflow, policy, and support
edge  -> private reachability, TLS termination, and transport metadata
```

One organization may provide several of these roles, but they are not the same
role. Keeping them conceptually separate makes migration and risk easier to
reason about.

## Deployment choices

| Deployment | Who runs the code? | Typical trust boundary | Best suited for |
| --- | --- | --- | --- |
| Local CLI or application | The user | The device, operating system, dependencies, and key storage | Development, technical users, and direct control |
| Application-embedded Acorn | The application operator or local app | Application code plus its execution environment | Products that need Acorn as a reusable kernel |
| Trusted hosted provider | A service provider such as Safebox | Provider operations and any key access the provider holds | Users who value support and web availability |
| Community-operated service | A household, team, or community | Community operator, policies, and infrastructure | Reciprocal resilience and shared operational support |
| FreeBSD jail or appliance | User or trusted operator | Host system, jail boundary, service configuration, and backups | Isolated, repeatable, appliance-style operation |
| Hardware-protected future model | User or provider with constrained hardware | Hardware, firmware, and permitted signing/decryption interface | Stronger key custody and limited key exposure |

These models can coexist. A user may begin with a trusted provider, keep an
independent encrypted replica, later restore locally, and eventually move key
operations into protected hardware.

## The trusted operator

The trusted operator is whoever supplies the running code or execution
environment for a particular Acorn instance. It may be:

- the user;
- a family member or community administrator;
- an employer or professional organization;
- a hosted service provider;
- a FreeBSD appliance operator; or
- an application such as Safebox.

If the operator can read or exercise the private key, the user is delegating
substantial operational authority. Encryption at the relay does not protect
against compromised code that already has access to the key and plaintext.

If keys remain local, hardware-held, or available only through constrained
operations, a provider may run more of the service without holding the entire
authority boundary. Acorn's protocol model is intended to support movement in
that direction, but hardware custody remains future work.

## Layered network trust

A hosted Acorn service may be private on one machine while a reverse proxy on
another machine supplies its public HTTPS endpoint. A VPN such as Tailscale can
provide authenticated, encrypted reachability between those machines. The
reverse proxy terminates public TLS and forwards an internal HTTP request to
the application.

Those facts create two separate controls:

```text
bind address             -> who can establish a network connection
trusted proxy allowlist  -> who may describe the original browser transport
```

Listening on `0.0.0.0` does not mean that every caller is trusted as a proxy.
It makes a port reachable on every host interface, subject to the VPN, host
firewall, and access policy. The application should separately accept
`X-Forwarded-Proto`, client-address, and host information only from the exact
reverse proxy or a narrowly scoped proxy network.

This layered approach is useful even inside a trusted community or household
VPN. The VPN establishes membership and protects the path; the proxy allowlist
assigns a specific service role. A peer that can reach the application is not
automatically authorized to claim that a request arrived over public HTTPS.

The architecture should be verified in both directions: a direct internal HTTP
request must be rejected, while the same request from the designated proxy with
trusted HTTPS metadata must succeed. This negative test is as important as the
successful public request.

## Acorn as a tenant and a client

The same Acorn wallet has different relationships with different providers:

- On a relay, it is an **encrypted tenant** whose events receive availability.
- At a mint, it is a **client** holding value issued and validated by that mint.
- Inside a hosted product, it is a **private component** running in an
  operator-provided execution environment.

A relay does not become the mint. A mint does not become the private-record
store. The application does not need to become the permanent custodian of the
wallet keys or protocol state.

## Safebox as a service surface

Safebox can build a supported web product around Acorn. It may provide
onboarding, sessions, a web presence, Lightning addresses, selected relays and
mints, monitoring, backups, and customer support.

Those services make Acorn usable without requiring every person to administer
servers. The design remains user-controlled when the user retains a practical
path to recover the component keys and compatible state through another
environment.

## Choosing a deployment

The right model depends on what must be protected and from whom:

- For experimentation, a local environment and small test balance may be
  sufficient.
- For sensitive records, private or firewalled relay infrastructure can reduce
  exposure alongside application-layer encryption.
- For supported use, a trusted provider may offer a better operational outcome
  than poorly maintained self-hosting.
- For continuity, replicas should not share every physical and administrative
  failure domain.
- For high-value keys, mature hardware isolation and reviewed operational
  procedures would be necessary before relying on Acorn at that level.

## Questions every deployment should answer

1. Who can access or exercise the private key?
2. Who controls the running code and its updates?
3. Where is encrypted state stored and replicated?
4. Which mint is authoritative for the wallet's proofs?
5. How can the user recover if the operator disappears?
6. What metadata remains visible to relays and networks?
7. What is monitored, backed up, tested, and documented?
8. Which network peer is authorized to assert public transport and client
   metadata?

User-controlled architecture is not a single hosting prescription. It is the
discipline of answering these questions while keeping continuity portable.

[Review the project status](project-status.md){ .md-button .md-button--primary }
[Return to relay availability](relay-availability-and-reciprocal-resilience.md){ .md-button }

## Reference basis

- [Acorn Component Boundary](https://github.com/trbouma/safebox-acorn/blob/main/docs/ACORN-COMPONENT-BOUNDARY.md)
- [Safebox Application Boundary](https://github.com/trbouma/safebox-acorn/blob/main/docs/SAFEBOX-APP-BOUNDARY.md)
- [FreeBSD Jail Installation](https://github.com/trbouma/safebox-acorn/blob/main/docs/FREEBSD-JAIL-INSTALL.md)
- [Acorn Product North Star](https://github.com/trbouma/safebox-acorn/blob/main/docs/ACORN-PRODUCT-NORTH-STAR.md)
- [Safebox Web Tailscale Reverse-Proxy Deployment](https://github.com/trbouma/safebox-web/blob/main/docs/TAILSCALE-REVERSE-PROXY-DEPLOYMENT.md)
