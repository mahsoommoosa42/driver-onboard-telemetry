# Analysis lessons

- Never reuse video offsets from different source clips. Validate early, middle and late anchors.
- A driver’s own live delta is not automatically a delta against another driver.
- Compare the same physical track positions, never equal elapsed time or normalized lap percentage.
- Withdraw segment allocations when synchronization changes; recompute all downstream results.
- Separate an initiating loss from its recovery; do not infer hesitation from speed alone.
- Account for different cars, setup, tyres and conditions before assigning gains to driver learning.
- Internal GPS glitches do not automatically invalidate a larger segment: assess the entry and exit anchors independently. If those anchors are uncertain, report the segment estimate with matching uncertainty.
