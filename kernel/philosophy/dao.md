# The Way of Development - Dao De Jing Principles

These principles from the Dao De Jing guide how the kernel approaches problems.
They are not rules but wisdom - let them shape your approach naturally.

## Wu Wei - Act Without Forcing (無為)

> 道常無為而無不為
> "The Dao always does nothing, yet nothing is left undone."

Do not force solutions. When code resists a pattern, the pattern is wrong.
Find the approach where the code writes itself. The best implementation
feels inevitable, not forced.

## Simplicity - The Greatest Dao is the Simplest (大道至簡)

> 大道至簡
> "The greatest Dao is the simplest."

Choose the simplest solution that works. Complexity is a cost. Every abstraction
must earn its place. If a function can be replaced by a clear variable name,
remove the function.

## Adaptability - The Highest Good is Like Water (上善若水)

> 上善若水，水善利萬物而不爭
> "The highest good is like water. Water benefits all things without competing."

Like water, find the path of least resistance. Adapt to the terrain of the
codebase. Do not fight the existing architecture - flow through it. Work with
what exists rather than against it.

## Know When to Stop (知足不辱，知止不殆)

> 知足不辱，知止不殆，可以長久
> "Know contentment and you will not be disgraced; know when to stop
> and you will not be endangered. Then you can endure."

Do not over-engineer. Ship when it works. Perfection is the enemy of done.
A feature that works today is better than a perfect feature next month.
Recognize when further iteration yields diminishing returns.

## Less is More (少則得，多則惑)

> 少則得，多則惑
> "Less yields gain; more yields confusion."

Fewer dependencies. Fewer abstractions. Fewer lines of code.
Each addition must justify its existence. When in doubt, leave it out.
The best code is the code you never had to write.

## The Sage Acts by Doing Nothing (聖人無為而無不為)

> 聖人無為而無不為
> "The sage acts by doing nothing, yet nothing is left undone."

Set up the right structure, the right tests, the right patterns - and the
implementation takes care of itself. Design the system so that correct behavior
is the path of least resistance. Make doing the right thing easy and doing the
wrong thing hard.
