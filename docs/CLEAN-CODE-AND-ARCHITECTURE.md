# Clean Code & Software Architecture — A Senior Engineer's Field Guide

> **Purpose of this document.** This is a self-contained reference distilled from the
> canonical literature on clean code and software architecture. It is written so that a
> reader (human *or* an LLM) with **no prior context** can absorb it and reason like an
> experienced senior architect: making sound trade-offs, spotting code smells, and
> structuring systems that survive change.
>
> Every section gives you (1) the **principle**, (2) **why it matters**, and (3) a **small
> concrete example** — usually Python (matching this project), occasionally
> language-neutral pseudocode. Read top to bottom once; thereafter use it as a checklist.

**Mental model to hold throughout:** *Software exists to be changed.* Almost every rule
below is ultimately about lowering the cost of the next change — making code easy to read,
easy to reason about locally, and easy to modify without fear.

---

## Table of Contents

1. [Foundational Heuristics (DRY · KISS · YAGNI · Boy Scout)](#1-foundational-heuristics)
2. [Clean Code at the Function & Naming Level](#2-clean-code-functions--naming)
3. [SOLID — Object-Oriented Design Principles](#3-solid)
4. [Refactoring & Code Smells](#4-refactoring--code-smells)
5. [Architecture: Clean / Hexagonal / Onion](#5-architecture-clean--hexagonal--onion)
6. [Domain-Driven Design (DDD) Building Blocks](#6-domain-driven-design)
7. [Error Handling & Boundaries](#7-error-handling--boundaries)
8. [Testing as a Design Force](#8-testing-as-a-design-force)
9. [The Senior Architect's Decision Framework](#9-decision-framework)
10. [Quick Review Checklist](#10-quick-review-checklist)
11. [Sources & Canon](#11-sources--canon)

---

## 1. Foundational Heuristics

These are the four "always on" rules. They are cheap to state and pay off everywhere.

### DRY — Don't Repeat Yourself
*"Every piece of knowledge must have a single, unambiguous, authoritative representation."*
— Hunt & Thomas, *The Pragmatic Programmer*.

DRY is about **knowledge**, not text. Two snippets that look identical but represent
*different decisions* are not duplication — and deduplicating them couples things that
should change independently. Conversely, the same business rule expressed in three places
is duplication even if the code looks different.

```python
# ❌ The tax rule lives in three places — change it and you must find all three.
price_with_tax = price * 1.1
invoice_total  = subtotal * 1.1
display_price  = base * 1.1

# ✅ One authoritative representation.
TAX_RATE = 0.10
def with_tax(amount: float) -> float:
    return amount * (1 + TAX_RATE)
```

> ⚠️ **DRY's trap:** premature deduplication. Prefer a little duplication over the *wrong*
> abstraction. "Duplication is far cheaper than the wrong abstraction" (Sandi Metz).

### KISS — Keep It Simple
Prefer the readable solution over the clever one. Code is read far more often than written.

```python
# ❌ Clever, write-only.
fact = lambda n: 1 if n <= 1 else n * (lambda f: f(f, n - 1))(...)

# ✅ Boring and obvious.
def factorial(n: int) -> int:
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result
```

### YAGNI — You Aren't Gonna Need It
Don't build for speculative future requirements. Build what is needed now, but keep it
*clean enough* that adding the future thing later is cheap. Flexibility you don't use is
just complexity you pay for.

### The Boy Scout Rule
*"Leave the code cleaner than you found it."* Small, opportunistic improvements (a clearer
name, an extracted function) compound over time and prevent rot.

---

## 2. Clean Code: Functions & Naming

Source: Robert C. Martin, *Clean Code*.

### Naming
- Names should reveal **intent**. If a name needs a comment to explain it, the name is wrong.
- Avoid disinformation, magic numbers, and meaningless distinctions (`data`, `info`, `tmp`).
- Follow the language convention: `snake_case` in Python, `camelCase` in Java/JS.

```python
# ❌
def calc(d, t): ...        # what is d? what is t?
if status == 2: ...        # what is 2?

# ✅
def days_between(start: date, end: date) -> int: ...

class OrderStatus(Enum):
    PENDING = 1
    SHIPPED = 2
if order.status is OrderStatus.SHIPPED: ...
```

### Functions
- **Small.** A function should do one thing, at one level of abstraction.
- **Few arguments.** 0–2 ideal; 3+ is a smell — consider grouping into an object.
- **No hidden side effects.** A function named `validate_password` must not also log the
  user in.
- **Command/Query Separation:** a function either *does* something (command, returns
  nothing meaningful) or *answers* something (query, returns a value) — not both.

```python
# ❌ Does too many things at two abstraction levels, hidden side effect.
def process(order):
    if order.items == []:           # validation
        raise ValueError
    total = 0
    for i in order.items:           # calculation
        total += i.price * i.qty
    db.save(order)                  # persistence (side effect)
    send_email(order.user)          # notification (side effect)
    return total

# ✅ One thing per function; the orchestrator reads like prose.
def place_order(order: Order) -> None:
    _validate(order)
    order.total = _calculate_total(order)
    repository.save(order)
    notifier.order_placed(order)
```

### Comments
- The best comment is a name that makes the comment unnecessary.
- Comment the **"why"** (intent, trade-offs, links to tickets), never the **"what"**
  (the code already says what).

```python
# ❌ noise
i += 1  # increment i

# ✅ explains a non-obvious decision
# Binance rejects orders < 10 USDT notional; round up to the exchange minimum.
notional = max(notional, MIN_NOTIONAL)
```

---

## 3. SOLID

Five object-oriented design principles (Robert C. Martin). They attack the four classic
sicknesses of code: **rigidity** (hard to change), **fragility** (changes break unrelated
things), **immobility** (can't reuse), and **viscosity** (the wrong thing is easier than
the right thing).

### S — Single Responsibility Principle
*A class should have only one reason to change* — i.e., serve one actor/concern.

```python
# ❌ Three reasons to change: business rules, DB schema, report format.
class Employee:
    def calculate_pay(self): ...
    def save_to_db(self): ...
    def render_report(self): ...

# ✅ Split by concern.
class PayCalculator: ...      # changes when pay rules change
class EmployeeRepository: ... # changes when storage changes
class EmployeeReport: ...     # changes when reporting changes
```

### O — Open/Closed Principle
*Open for extension, closed for modification.* Add new behaviour by adding code, not by
editing existing, tested code. Achieve via polymorphism / strategy.

```python
# ❌ Every new exchange edits this function.
def fee(exchange, amt):
    if exchange == "binance": return amt * 0.001
    if exchange == "bybit":   return amt * 0.00075
    # ...keeps growing

# ✅ New exchange = new class, zero edits to existing code.
class FeeModel(Protocol):
    def fee(self, amount: float) -> float: ...

class BinanceFees:  # implements FeeModel
    def fee(self, amount): return amount * 0.001
class BybitFees:
    def fee(self, amount): return amount * 0.00075
```

### L — Liskov Substitution Principle
Subtypes must be usable anywhere their base type is expected, **without surprises**. If a
subclass weakens a guarantee or throws where the parent didn't, the hierarchy is wrong.

```python
# ❌ A read-only stream is NOT substitutable for a writable one.
class FileStream:
    def write(self, data): ...
class ReadOnlyStream(FileStream):
    def write(self, data):
        raise NotImplementedError   # violates LSP — callers break

# ✅ Model the capability honestly; don't inherit what you can't honor.
class Readable(Protocol):
    def read(self) -> bytes: ...
class Writable(Protocol):
    def write(self, data: bytes) -> None: ...
```

### I — Interface Segregation Principle
Clients should not be forced to depend on methods they don't use. Prefer many small,
focused interfaces over one fat one.

```python
# ❌ A simple printer is forced to implement fax/scan it can't do.
class Machine(Protocol):
    def print(self, doc): ...
    def scan(self, doc): ...
    def fax(self, doc): ...

# ✅ Segregate.
class Printer(Protocol):
    def print(self, doc): ...
class Scanner(Protocol):
    def scan(self, doc): ...
```

### D — Dependency Inversion Principle
High-level policy should not depend on low-level details; both depend on **abstractions**.
This is the principle that makes the architecture in §5 possible.

```python
# ❌ Trading logic hard-wired to a concrete exchange SDK.
class TradingEngine:
    def __init__(self):
        self.client = BinanceClient()   # high-level depends on low-level

# ✅ Depend on an abstraction; inject the concrete one.
class Exchange(Protocol):
    def place_order(self, order: Order) -> OrderResult: ...

class TradingEngine:
    def __init__(self, exchange: Exchange):   # inverted; testable, swappable
        self.exchange = exchange
```

---

## 4. Refactoring & Code Smells

Source: Martin Fowler, *Refactoring* (2nd ed.).

**Refactoring** = changing the structure of code *without changing its behaviour*, in small
verified steps, with tests as the safety net. You refactor to make a change easy, then make
the easy change.

Common **code smells** → their typical refactoring:

| Smell | What you see | Fix |
|---|---|---|
| Long Function | 50+ lines, many responsibilities | **Extract Function** |
| Long Parameter List | 4+ params | **Introduce Parameter Object** |
| Primitive Obsession | `str` / `float` everywhere for domain ideas | **Replace with Value Object** (§6) |
| Feature Envy | method uses another object's data more than its own | **Move Function** |
| Shotgun Surgery | one change touches many files | consolidate the responsibility |
| Divergent Change | one file changes for many reasons | split it (SRP) |
| Switch on type | `if type == ...` chains | **Replace Conditional with Polymorphism** (OCP) |
| Comments explaining bad code | apologetic comments | fix the code instead |

```python
# Extract Function — the most common refactoring.
# Before: a comment is a hint that a block wants a name.
def print_owing(invoice):
    outstanding = sum(o.amount for o in invoice.orders)
    # print banner
    print("***********")
    print("** Owing **")
    print("***********")
    print(f"name: {invoice.customer}")
    print(f"amount: {outstanding}")

# After:
def print_owing(invoice):
    outstanding = _outstanding(invoice)
    _print_banner()
    _print_details(invoice, outstanding)
```

---

## 5. Architecture: Clean / Hexagonal / Onion

These three names describe **the same core idea** with different vocabulary: keep your
**business logic at the center**, independent of frameworks, databases, UIs, and external
services. Dependencies always point **inward**, toward the domain. This is the
Dependency Inversion Principle (§3) applied at system scale.

```
          ┌─────────────────────────────────────────────┐
          │   Infrastructure / Adapters (outermost)       │   ← DB, HTTP, exchange SDKs, UI
          │   ┌───────────────────────────────────────┐   │
          │   │   Application Layer (use cases)          │   │   ← orchestration, ports
          │   │   ┌───────────────────────────────┐     │   │
          │   │   │      Domain (innermost)          │     │   │   ← entities, value objects,
          │   │   │   pure business rules            │     │   │      domain services. NO imports
          │   │   └───────────────────────────────┘     │   │      of frameworks/IO.
          │   └───────────────────────────────────────┘   │
          └─────────────────────────────────────────────┘
                 Dependencies point INWARD  ───────▶
```

### The layers
- **Domain (center):** entities, value objects, domain services. Pure logic. Knows nothing
  about HTTP, SQL, JSON, or any vendor. *If you deleted your web framework and database, this
  layer would still compile and make sense.*
- **Application / Use Cases:** orchestrates the domain to fulfill a user intent ("place
  order", "run backtest"). Declares **ports** (interfaces) for what it needs from the
  outside world.
- **Infrastructure / Adapters (edge):** concrete implementations of the ports — the Postgres
  repository, the Binance REST client, the Streamlit dashboard, the CLI.

### Ports & Adapters (Hexagonal vocabulary)
- A **port** is an interface owned by the inside (e.g., `OrderRepository`, `Exchange`).
- An **adapter** is an outside implementation of that port (e.g., `PostgresOrderRepository`,
  `BinanceExchange`).
- The application talks to ports; adapters are wired in at startup (composition root) via
  dependency injection.

```python
# Port (declared in the application/domain layer — the "inside")
class OrderRepository(Protocol):
    def save(self, order: Order) -> None: ...
    def by_id(self, id: OrderId) -> Order | None: ...

# Use case depends only on the port.
class PlaceOrder:
    def __init__(self, repo: OrderRepository, exchange: Exchange):
        self._repo, self._exchange = repo, exchange
    def execute(self, cmd: PlaceOrderCommand) -> OrderId:
        order = Order.create(cmd.symbol, cmd.qty)   # domain logic
        self._exchange.place(order)
        self._repo.save(order)
        return order.id

# Adapter (infrastructure — the "outside"), swappable & mockable.
class PostgresOrderRepository:   # implements OrderRepository
    def save(self, order): ...
    def by_id(self, id): ...
```

**Why this pays off:** the domain is testable without a DB or network; you can swap
Postgres for SQLite, or Binance for a paper-trading mock, by writing a new adapter — no
change to business logic. Frameworks become *plugins*, not foundations.

**Practical guidance (from the field):** combine the *strengths* of Clean/Hexagonal/DDD
rather than following any one dogmatically. Add layers when complexity justifies them; a
small script does not need four rings. Match the architecture to the problem's size.

---

## 6. Domain-Driven Design

Source: Eric Evans, *Domain-Driven Design*; curated practices from
[Sairyss/domain-driven-hexagon](https://github.com/Sairyss/domain-driven-hexagon).

DDD is about modeling **complex business domains** so the code speaks the language of the
business. Use it where the domain is genuinely complex; skip the ceremony for CRUD.

### Ubiquitous Language
Developers and domain experts share **one vocabulary**, and that vocabulary appears
verbatim in the code (`Position`, `StopLoss`, `Drawdown` — not `data1`, `flag`).

### Value Objects
Small immutable types that replace primitives and carry validation + behaviour. Compared by
**value**, not identity. They kill "primitive obsession."

```python
# ❌ Primitive obsession: a price is just a float — no validation, no meaning.
def place(symbol: str, price: float): ...

# ✅ Value Object: immutable, self-validating, comparable by value.
@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str
    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Money cannot be negative")
    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError("currency mismatch")
        return Money(self.amount + other.amount, self.currency)
```

### Entities
Objects with a stable **identity** over time (an `Order` is the same order even as its state
changes). Protect invariants: **private setters, mutate via methods, validate on creation,
no anaemic no-arg constructors.**

```python
class Order:
    def __init__(self, id: OrderId, items: list[LineItem]):
        if not items:
            raise ValueError("Order needs at least one item")  # invariant on creation
        self._id, self._items, self._status = id, items, OrderStatus.PENDING

    def ship(self) -> None:                 # state changes via intention-revealing methods
        if self._status is not OrderStatus.PAID:
            raise InvalidStateError("cannot ship an unpaid order")
        self._status = OrderStatus.SHIPPED
```

### Aggregates & Aggregate Roots
An **aggregate** is a cluster of entities/value objects treated as one consistency unit. The
**aggregate root** is the single entry point; outsiders reference internal entities **by ID
only**. Keep aggregates **small** (large ones cause locking/performance pain).

### Bounded Context
A boundary within which a model and its language are consistent. "Account" in *Billing*
≠ "Account" in *Trading*. Different contexts get different models; integrate across them via
an **Anti-Corruption Layer** (a translation adapter) so one context's mess doesn't leak into
another.

### Commands vs. Queries (CQRS-lite)
Separate state-changing operations (**commands**, return minimal metadata like an ID) from
reads (**queries**, which may bypass the domain and hit a read-optimized model directly).

### DTOs (Data Transfer Objects)
Keep API/persistence shapes **separate** from domain entities. Whitelist the fields you
expose (prevents accidental data leaks) and keep the contract stable even when the domain
model evolves internally.

---

## 7. Error Handling & Boundaries

- **Prefer exceptions over error codes** for unrecoverable conditions; codes get ignored and
  clutter call sites.
- **Distinguish validation from guarding.** *Validation* filters untrusted input at the
  boundary (return rich errors to the caller). *Guarding* is a defensive assertion inside the
  domain that a thing that "can't happen" indeed didn't.
- For **recoverable** outcomes that are part of normal flow, an explicit result type
  (`Result`/`Either`, or a typed return) is often clearer than throwing.
- **Domain errors are not HTTP errors.** Define a domain error hierarchy
  (`InsufficientFunds`, `MarketClosed`) independent of transport; let an outer adapter map
  them to HTTP/CLI codes.
- **Never swallow exceptions silently.** Fail loud, log with context, or propagate.

```python
# ❌ Silent swallow — bugs vanish.
try:
    risky()
except Exception:
    pass

# ✅ Handle what you can, attach context, re-raise the rest.
try:
    risky()
except RateLimitError as e:
    logger.warning("exchange throttled; backing off", exc_info=e)
    backoff()
```

---

## 8. Testing as a Design Force

Tests are not just verification — *hard-to-test code is a design smell*. If you can't test a
unit without spinning up a database or network, your dependencies aren't inverted (§3, §5).

- **Test behaviour, not implementation.** Assert on outcomes, not internal call sequences.
- **Arrange–Act–Assert.** One logical assertion per test; a name that states the scenario.
- **The test pyramid:** many fast unit tests, fewer integration tests, very few slow E2E
  tests.
- **Mock at the ports.** Because the domain depends on interfaces, you inject fakes/mocks for
  the exchange, the repository, the clock — and test pure logic in milliseconds.
- **Test both the happy path and the failure paths.**

```python
def test_cannot_ship_unpaid_order():
    order = Order(OrderId("1"), [LineItem("BTC", qty=1)])  # PENDING
    with pytest.raises(InvalidStateError):
        order.ship()
```

---

## 9. Decision Framework

How a senior reasons when the rules seem to conflict. Rules are heuristics, not laws — the
job is judgment.

1. **Optimize for change, not for cleverness.** Ask: "What is most likely to change, and how
   painful will it be?" Put seams (interfaces) where change is likely; keep the unlikely
   simple.
2. **Match ceremony to complexity.** Full hexagonal + DDD for a core trading engine; a plain
   function for a one-off script. Over-architecting is as costly as under-architecting.
3. **Couple things that change together; decouple things that change independently.** This is
   the deeper truth behind SRP, DRY, and Bounded Contexts. *Cohesion high, coupling low.*
4. **Make the dependency arrows point toward stability.** Stable, abstract things (domain
   rules) should not depend on volatile, concrete things (vendors, frameworks).
5. **Prefer explicit over implicit.** Explicit dependencies (injected), explicit errors,
   explicit state transitions. Magic is convenient until you debug it.
6. **Defer decisions you can't yet make well.** Good architecture *keeps options open*
   (YAGNI + clean boundaries) rather than guessing the future.
7. **Leave a trail.** Record non-obvious trade-offs (an ADR, a "why" comment). The next
   engineer — or LLM — inherits your reasoning, not just your code.

> **The one-sentence summary:** *A good architecture maximizes the number of decisions NOT
> made, and minimizes the cost of the decisions you must change.*

---

## 10. Quick Review Checklist

Use this when reviewing any diff or designing any module.

**Code level**
- [ ] Names reveal intent; no magic numbers; convention-consistent.
- [ ] Functions do one thing, at one abstraction level, with ≤3 args and no hidden side
      effects.
- [ ] Comments explain *why*, not *what*; no apologetic comments for bad code.
- [ ] No duplicated *knowledge* (but no premature/incorrect abstraction either).

**Design level (SOLID)**
- [ ] Each class has one reason to change.
- [ ] New variants can be added without editing existing code (polymorphism over `if/switch`).
- [ ] Subtypes honor their base type's contract.
- [ ] Interfaces are small and client-specific.
- [ ] High-level code depends on abstractions, with concretes injected.

**Architecture level**
- [ ] Business logic has zero imports of frameworks / IO / vendor SDKs.
- [ ] Dependencies point inward; outside details sit behind ports.
- [ ] Domain concepts are value objects/entities, not bare primitives.
- [ ] Invariants are enforced inside the domain, not scattered across callers.
- [ ] Domain errors are independent of transport (HTTP/CLI) concerns.

**Safety net**
- [ ] Logic is unit-testable without a DB/network (mock at the ports).
- [ ] Both happy and failure paths are tested.
- [ ] Errors are handled or propagated with context — never silently swallowed.

---

## 11. Sources & Canon

**Books (the canon):**
- Robert C. Martin — *Clean Code* (2008) and *Clean Architecture* (2017).
- Martin Fowler — *Refactoring*, 2nd ed. (2018) — <https://martinfowler.com/books/refactoring.html>
- Andrew Hunt & David Thomas — *The Pragmatic Programmer*.
- Eric Evans — *Domain-Driven Design* (2003).
- Gamma, Helm, Johnson, Vlissides ("Gang of Four") — *Design Patterns* (1994).
- Alistair Cockburn — *Hexagonal Architecture* (Ports & Adapters), original article.

**Curated online references:**
- [Sairyss/domain-driven-hexagon](https://github.com/Sairyss/domain-driven-hexagon) —
  DDD + Hexagonal + Clean with runnable code examples.
- [awesome-software-architecture](https://github.com/mehdihadeli/awesome-software-architecture)
  — topic-indexed architecture resources.
- [martinfowler.com](https://martinfowler.com/) — refactoring, enterprise patterns, essays.
- [Clean Code Principles — Codacy](https://blog.codacy.com/clean-code-principles)
- [SOLID Principles — DigitalOcean](https://www.digitalocean.com/community/conceptual-articles/s-o-l-i-d-the-first-five-principles-of-object-oriented-design)
- [DDD / Clean / Hexagonal compared — Medium](https://medium.com/@ignatovich.dm/understanding-software-architecture-ddd-clean-architecture-and-hexagonal-architecture-13758e59c951)

---

*This guide is intentionally concise and example-driven. When the situation is ambiguous,
fall back to §9: optimize for the cost of the next change, and match ceremony to complexity.*
