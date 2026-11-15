# Reading queue

The synthetic project turns a short list of article topics into a sorted queue and a two-item preview. Run each step from the demo workspace root.

## U1. Build the queue

Sort topics and remove duplicate lines. The resulting queue should contain `birds`, `gardens`, and `trails`, in that order.

```sh
printf 'trails\nbirds\ntrails\ngardens\n' > topics.txt
LC_ALL=C sort -u topics.txt > queue.txt
printf 'birds\ngardens\ntrails\n' | cmp - queue.txt
```

## U2. Make a preview

Use the verified queue from U1. The preview should contain the first two topics.

```sh
head -n 2 queue.txt > preview.txt
printf 'birds\ngardens\n' | cmp - preview.txt
```
