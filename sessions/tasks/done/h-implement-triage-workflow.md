---
name: h-implement-triage-workflow
branch: feature/triage-workflow
status: complete
created: 2025-11-25
completed: 2025-11-25
depends_on:
  - h-implement-priority-scoring
submodules:
  - RepoRelay
---

# Implement Triage Workflow (Phase 2)

## Problem/Goal

Add triage workflow capabilities to the Finding model, integrate with existing auto-triage rules, and create an audit trail for triage decisions.

**Reference**: `sessions/docs/vulnerability-prioritization-strategy.md` - Part 4.1, 4.3

## Success Criteria
- [x] Add triage workflow fields to Finding model (triage_state, assigned_to, due_date, reason)
- [x] Add auto-triage tracking fields (auto_triage_rule, auto_triage_confidence)
- [x] Create TriageHistory model for audit trail
- [x] Integrate auto-triage rules with priority scoring
- [x] Create AutoTriageEngine service that runs rules and records history
- [x] Expose triage actions via REST API endpoints
- [x] Unit tests for triage state transitions
- [x] Backfill triage_state from existing under_review, risk_accepted flags

## Context Manifest

### How the Finding Model Currently Works: Existing Triage State Fields

The Finding model (`dojo/models.py:3280-3729`) is a massive 450-line model at the heart of DefectDojo's vulnerability management system. It already has **multiple overlapping triage-related flags** that need to be understood before adding new fields:

**Existing Status Flags (lines 3390-3420):**

When a finding is created, it starts with these default states:
```python
active = True              # Finding is currently relevant
verified = False           # Not manually verified by tester yet
false_p = False           # Not marked as false positive
duplicate = False         # Not a duplicate of another finding
out_of_scope = False      # Within scope of test/engagement
risk_accepted = False     # Not accepted as business risk
under_review = False      # Not currently being reviewed
is_mitigated = False      # Not yet fixed
```

These flags create a complex state machine with business rules enforced in the serializer (`dojo/api_v2/serializers.py:1831-1836`):
- Duplicate findings CANNOT be active or verified
- False positive findings CANNOT be verified
- The `last_status_update` timestamp auto-updates when any status field changes

**Existing Auto-Triage System (lines 3536-3555):**

DefectDojo ALREADY has an auto-triage system with three fields:
```python
auto_triage_decision = 'PENDING' | 'DISMISS' | 'ESCALATE' | 'ACCEPT_RISK'
auto_triage_reason = TextField (explanation)
auto_triaged_at = DateTimeField (timestamp)
```

The AutoTriageEngine (`dojo/auto_triage/engine.py`) evaluates 16 rules from `dojo/auto_triage/rules.py`:
- **Escalation rules** (lines 154-193): Critical/High EPSS in Tier 1/2 production repos
- **Risk acceptance rules** (lines 221-260): Archived repos, dormant low-risk findings
- **Dismissal rules** (lines 262-293): Very low EPSS in Tier 3/4, info severity

Rule evaluation is first-match-wins, with confidence scores 50-95. The engine updates findings via `_apply_triage_to_finding()` which saves only the three auto-triage fields using `update_fields=['auto_triage_decision', 'auto_triage_reason', 'auto_triaged_at']`.

**Priority Scoring (NEW - Phase 1, lines 3557-3578):**

Just added in migration 0259:
```python
priority_score = IntegerField(default=0, db_index=True)      # 0-1000+ range
priority_bucket = CharField('P0'|'P1'|'P2'|'P3'|'P4')       # Computed bucket
priority_calculated_at = DateTimeField                       # Last calc timestamp
```

The PriorityScorer (`dojo/finding/priority_scorer.py`) implements the formula from the strategy document:
```
PriorityScore = (TierWeight × SeverityScore) + Modifiers
```

Tier weights: tier1=5.0, tier2=3.5, tier3=2.0, tier4=1.0, archived=0.2
Severity scores: Critical=100, High=75, Medium=50, Low=25, Info=10
Modifiers: KEV +150, Ransomware +100, EPSS ≥0.7 +75, SLA breach +50, fix available +30, production signals +25, active webhooks +15, very low EPSS -50, no fix -20, dormant repo -40, no production -30

The `calculate_finding_priority_task` Celery task (lines 304-354) recalculates priority asynchronously, triggered on finding create/update.

**Critical Integration Point:**

The auto-triage system and priority scoring were built separately but need to work together. The current auto-triage engine does NOT use priority scores - it evaluates raw signals (EPSS, tier, severity) directly via lambda conditions in rules.py.

**The Problem:**

We now have:
1. Legacy status flags (`under_review`, `risk_accepted`, `out_of_scope`, `false_p`, etc.)
2. Auto-triage fields (`auto_triage_decision`, `auto_triage_reason`, `auto_triaged_at`)
3. Priority scoring fields (`priority_score`, `priority_bucket`, `priority_calculated_at`)

But NO unified triage workflow that:
- Tracks manual triage decisions (assigned_to, due_date, reason)
- Records triage history (who did what when)
- Integrates auto-triage rules with priority scores
- Provides state transitions (pending → escalated → assigned → resolved)

### For New Feature Implementation: What Needs to Connect

**Phase 2 adds manual triage workflow fields to Finding:**

```python
# New fields to add (spec lines 36-50):
triage_state = CharField(max_length=20, choices=[...], default='pending', db_index=True)
triage_assigned_to = ForeignKey(Dojo_User, null=True, on_delete=SET_NULL)
triage_due_date = DateField(null=True)
triage_reason = TextField(blank=True)
auto_triage_rule = CharField(max_length=100, blank=True)        # Which rule matched
auto_triage_confidence = IntegerField(null=True, validators=[0-100])
```

**Key Design Decisions:**

1. **Relationship to Existing `auto_triage_decision`:**
   - Keep existing field for backward compatibility
   - Map auto_triage_decision to triage_state during backfill migration
   - PENDING → 'pending', DISMISS → 'dismissed', ESCALATE → 'escalated', ACCEPT_RISK → 'accepted'

2. **Relationship to Existing Status Flags:**
   - `under_review` should map to triage_state='assigned' (if under_review=True, someone is working on it)
   - `risk_accepted` should map to triage_state='accepted' (risk formally accepted)
   - These old fields should remain for backward compatibility but become read-only in API

3. **Integration with AutoTriageEngine:**
   - Current engine updates `auto_triage_decision` field
   - NEW engine should ALSO update `triage_state`, `auto_triage_rule`, `auto_triage_confidence`
   - Rule execution should create TriageHistory records (action='auto_triaged')

4. **Integration with PriorityScorer:**
   - Auto-triage rules currently evaluate raw signals (EPSS, tier, severity)
   - AFTER Phase 2, rules COULD use priority_score directly: `lambda f: f.priority_score >= 500`
   - This simplifies rule logic and ensures consistency with dashboard

### New Model: TriageHistory

**Purpose:** Audit trail for all triage decisions (manual and automated)

**Pattern to Follow:** Similar to `NoteHistory` model (`dojo/models.py:745-755`) which tracks note edits:
```python
class NoteHistory(models.Model):
    note_type = ForeignKey(Note_Type, null=True, on_delete=CASCADE)
    data = TextField()
    time = DateTimeField(default=get_current_datetime, editable=False)
    current_editor = ForeignKey(Dojo_User, editable=False, null=True, on_delete=CASCADE)
```

**TriageHistory Design (spec lines 52-64):**

```python
class TriageHistory(models.Model):
    finding = ForeignKey(Finding, on_delete=CASCADE, related_name="triage_history")
    action = CharField(max_length=20, choices=[
        ('created', 'Created'),
        ('auto_triaged', 'Auto-Triaged'),
        ('escalated', 'Escalated'),
        ('assigned', 'Assigned'),
        ('deferred', 'Deferred'),
        ('accepted', 'Risk Accepted'),
        ('dismissed', 'Dismissed'),
        ('reopened', 'Reopened'),
    ])
    previous_state = CharField(max_length=20, blank=True)     # Old triage_state
    new_state = CharField(max_length=20)                      # New triage_state
    reason = TextField(blank=True)                            # User-provided reason
    rule_name = CharField(max_length=100, blank=True)         # Auto-triage rule name
    confidence = IntegerField(null=True, validators=[0-100])  # Auto-triage confidence
    performed_by = ForeignKey(Dojo_User, null=True, on_delete=SET_NULL)
    performed_at = DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-performed_at']
        verbose_name = "Triage History"
        verbose_name_plural = "Triage History"
```

**When to Create Records:**

1. **Finding creation:** action='created', new_state='pending', performed_by=reporter
2. **Auto-triage:** action='auto_triaged', rule_name populated, confidence score
3. **Manual escalation:** action='escalated', reason required, performed_by=current_user
4. **Assignment:** action='assigned', triage_assigned_to updated, performed_by=assigner
5. **Risk acceptance:** action='accepted', reason required (links to Risk_Acceptance record if exists)
6. **Dismissal:** action='dismissed', reason required
7. **Reopening:** action='reopened', reason optional

### REST API Endpoints

**Pattern to Follow:** FindingViewSet.close() action (`dojo/api_v2/views.py:928-958`)

This is a custom DRF action on the FindingViewSet that:
```python
@extend_schema(
    methods=["POST"],
    request=serializers.FindingCloseSerializer,
    responses={status.HTTP_200_OK: serializers.FindingCloseSerializer},
)
@action(detail=True, methods=["post"])
def close(self, request, pk=None):
    finding = self.get_object()  # Uses DRF's built-in permission checking

    # Validate input
    serializer = serializers.FindingCloseSerializer(data=request.data)
    if serializer.is_valid():
        # Delegate to helper function
        finding_helper.close_finding(
            finding=finding,
            user=request.user,
            is_mitigated=serializer.validated_data["is_mitigated"],
            note_entry=serializer.validated_data.get("note"),
            # ... more params
        )
        return Response(serializer.data)
    else:
        return Response(serializer.errors, status=400)
```

**New API Actions to Add (spec lines 59-62):**

1. **POST `/api/v2/findings/{id}/triage/`** - Perform triage action
   ```python
   @action(detail=True, methods=["post"])
   def triage(self, request, pk=None):
       # Input: action, reason, assigned_to, due_date
       # Validates state transitions
       # Creates TriageHistory record
       # Updates Finding.triage_state, triage_assigned_to, etc.
       # Returns updated finding
   ```

2. **GET `/api/v2/findings/{id}/triage_history/`** - Get triage history
   ```python
   @action(detail=True, methods=["get"])
   def triage_history(self, request, pk=None):
       # Returns TriageHistory queryset for finding
       # Uses TriageHistorySerializer
       # Ordered by performed_at descending
   ```

3. **POST `/api/v2/findings/bulk_triage/`** - Bulk triage actions
   ```python
   @action(detail=False, methods=["post"])  # detail=False for list-level action
   def bulk_triage(self, request):
       # Input: finding_ids[], action, reason, assigned_to, due_date
       # Validates permissions for each finding
       # Applies triage action to all
       # Returns success/failure count
   ```

**Serializers to Create:**

1. **TriageHistorySerializer:**
   ```python
   class TriageHistorySerializer(serializers.ModelSerializer):
       performed_by = serializers.PrimaryKeyRelatedField(read_only=True)

       class Meta:
           model = TriageHistory
           fields = '__all__'
   ```

2. **TriageActionSerializer:**
   ```python
   class TriageActionSerializer(serializers.Serializer):
       action = serializers.ChoiceField(choices=['escalate', 'assign', 'defer', 'accept', 'dismiss'])
       reason = serializers.CharField(required=False, allow_blank=True)
       assigned_to = serializers.PrimaryKeyRelatedField(
           queryset=Dojo_User.objects.all(),
           required=False,
           allow_null=True
       )
       due_date = serializers.DateField(required=False, allow_null=True)

       def validate(self, data):
           # Require reason for 'accept' and 'dismiss' actions
           if data['action'] in ['accept', 'dismiss'] and not data.get('reason'):
               raise serializers.ValidationError("Reason is required for accept/dismiss actions")
           # Require assigned_to for 'assign' action
           if data['action'] == 'assign' and not data.get('assigned_to'):
               raise serializers.ValidationError("assigned_to is required for assign action")
           return data
   ```

3. **BulkTriageSerializer:**
   ```python
   class BulkTriageSerializer(serializers.Serializer):
       finding_ids = serializers.ListField(
           child=serializers.IntegerField(),
           min_length=1
       )
       action = serializers.ChoiceField(choices=['escalate', 'assign', 'defer', 'accept', 'dismiss'])
       reason = serializers.CharField(required=False, allow_blank=True)
       assigned_to = serializers.PrimaryKeyRelatedField(
           queryset=Dojo_User.objects.all(),
           required=False,
           allow_null=True
       )
       due_date = serializers.DateField(required=False, allow_null=True)
   ```

### Integration with AutoTriageEngine

**Current Engine Behavior (`dojo/auto_triage/engine.py`):**

The `_apply_triage_to_finding()` method (lines 200-236):
```python
def _apply_triage_to_finding(self, finding: Finding):
    # Get triage decision
    decision_data = self.triage_single_finding(finding)

    # Skip if decision unchanged
    if finding.auto_triage_decision == decision_data['decision']:
        return

    # Apply decision
    with transaction.atomic():
        finding.auto_triage_decision = decision_data['decision']
        finding.auto_triage_reason = f"{decision_data['reason']} (Rule: {decision_data['rule_name']}, Confidence: {decision_data['confidence']}%)"
        finding.auto_triaged_at = timezone.now()
        finding.save(update_fields=['auto_triage_decision', 'auto_triage_reason', 'auto_triaged_at'])
```

**What Needs to Change:**

1. **Also update new triage workflow fields:**
   ```python
   finding.triage_state = self._map_decision_to_state(decision_data['decision'])
   finding.auto_triage_rule = decision_data['rule_name']
   finding.auto_triage_confidence = decision_data['confidence']
   finding.save(update_fields=[
       'auto_triage_decision',     # Legacy field
       'auto_triage_reason',       # Legacy field
       'auto_triaged_at',         # Legacy field
       'triage_state',            # NEW
       'auto_triage_rule',        # NEW
       'auto_triage_confidence'   # NEW
   ])
   ```

2. **Create TriageHistory record:**
   ```python
   TriageHistory.objects.create(
       finding=finding,
       action='auto_triaged',
       previous_state=finding.triage_state,
       new_state=new_state,
       reason=decision_data['reason'],
       rule_name=decision_data['rule_name'],
       confidence=decision_data['confidence'],
       performed_by=None,  # System action
       performed_at=timezone.now()
   )
   ```

3. **Helper function for decision mapping:**
   ```python
   def _map_decision_to_state(self, decision: str) -> str:
       """Map auto_triage_decision to triage_state."""
       mapping = {
           'PENDING': 'pending',
           'DISMISS': 'dismissed',
           'ESCALATE': 'escalated',
           'ACCEPT_RISK': 'accepted',
       }
       return mapping.get(decision, 'pending')
   ```

### Database Migration Strategy

**Migration 1: Add New Fields to Finding Model**

```python
# migrations/0260_finding_triage_workflow_fields.py
operations = [
    migrations.AddField(
        model_name='finding',
        name='triage_state',
        field=models.CharField(
            max_length=20,
            choices=[
                ('pending', 'Pending Triage'),
                ('escalated', 'Escalated'),
                ('assigned', 'Assigned'),
                ('deferred', 'Deferred'),
                ('accepted', 'Risk Accepted'),
                ('dismissed', 'Dismissed'),
            ],
            default='pending',
            db_index=True,
        ),
    ),
    migrations.AddField(
        model_name='finding',
        name='triage_assigned_to',
        field=models.ForeignKey(
            null=True,
            blank=True,
            on_delete=models.SET_NULL,
            to='dojo.Dojo_User',
            related_name='assigned_findings',
        ),
    ),
    migrations.AddField(
        model_name='finding',
        name='triage_due_date',
        field=models.DateField(null=True, blank=True),
    ),
    migrations.AddField(
        model_name='finding',
        name='triage_reason',
        field=models.TextField(blank=True),
    ),
    migrations.AddField(
        model_name='finding',
        name='auto_triage_rule',
        field=models.CharField(max_length=100, blank=True),
    ),
    migrations.AddField(
        model_name='finding',
        name='auto_triage_confidence',
        field=models.IntegerField(
            null=True,
            blank=True,
            validators=[MinValueValidator(0), MaxValueValidator(100)],
        ),
    ),
]
```

**Migration 2: Create TriageHistory Model**

```python
# migrations/0261_triage_history_model.py
operations = [
    migrations.CreateModel(
        name='TriageHistory',
        fields=[
            ('id', models.AutoField(auto_created=True, primary_key=True)),
            ('action', models.CharField(max_length=20, choices=[...])),
            ('previous_state', models.CharField(max_length=20, blank=True)),
            ('new_state', models.CharField(max_length=20)),
            ('reason', models.TextField(blank=True)),
            ('rule_name', models.CharField(max_length=100, blank=True)),
            ('confidence', models.IntegerField(null=True, validators=[...])),
            ('performed_at', models.DateTimeField(auto_now_add=True)),
            ('finding', models.ForeignKey(
                on_delete=models.CASCADE,
                to='dojo.Finding',
                related_name='triage_history'
            )),
            ('performed_by', models.ForeignKey(
                null=True,
                on_delete=models.SET_NULL,
                to='dojo.Dojo_User'
            )),
        ],
        options={
            'ordering': ['-performed_at'],
            'verbose_name': 'Triage History',
            'verbose_name_plural': 'Triage History',
        },
    ),
]
```

**Migration 3: Data Backfill (RunPython)**

```python
# migrations/0262_backfill_triage_state.py
def backfill_triage_state(apps, schema_editor):
    """
    Backfill triage_state from existing flags:
    - risk_accepted=True → 'accepted'
    - under_review=True → 'assigned'
    - auto_triage_decision='DISMISS' → 'dismissed'
    - auto_triage_decision='ESCALATE' → 'escalated'
    - auto_triage_decision='ACCEPT_RISK' → 'accepted'
    - Otherwise → 'pending'
    """
    Finding = apps.get_model('dojo', 'Finding')

    # Risk accepted findings
    Finding.objects.filter(risk_accepted=True).update(triage_state='accepted')

    # Under review findings (not risk accepted)
    Finding.objects.filter(
        under_review=True,
        risk_accepted=False
    ).update(triage_state='assigned')

    # Auto-triaged findings
    Finding.objects.filter(auto_triage_decision='DISMISS').update(triage_state='dismissed')
    Finding.objects.filter(auto_triage_decision='ESCALATE').update(triage_state='escalated')
    Finding.objects.filter(
        auto_triage_decision='ACCEPT_RISK',
        risk_accepted=False  # Don't double-update
    ).update(triage_state='accepted')

operations = [
    migrations.RunPython(backfill_triage_state, migrations.RunPython.noop),
]
```

### Technical Reference Details

#### File Locations for Implementation

**Model Changes:**
- `dojo/models.py` - Add triage workflow fields to Finding model (after line 3578)
- `dojo/models.py` - Add TriageHistory model (after Risk_Acceptance model at line 4780)

**AutoTriageEngine Updates:**
- `dojo/auto_triage/engine.py` - Modify `_apply_triage_to_finding()` method (line 200)
- `dojo/auto_triage/engine.py` - Add `_map_decision_to_state()` helper
- `dojo/auto_triage/engine.py` - Add TriageHistory record creation

**API Implementation:**
- `dojo/api_v2/views.py` - Add custom actions to FindingViewSet (after line 958)
  - `@action(detail=True) def triage()`
  - `@action(detail=True) def triage_history()`
  - `@action(detail=False) def bulk_triage()`
- `dojo/api_v2/serializers.py` - Add serializers (after FindingSerializer at line 1836)
  - `TriageHistorySerializer`
  - `TriageActionSerializer`
  - `BulkTriageSerializer`

**Database Migrations:**
- `dojo/db_migrations/0260_finding_triage_workflow_fields.py` - Add fields
- `dojo/db_migrations/0261_triage_history_model.py` - Create model
- `dojo/db_migrations/0262_backfill_triage_state.py` - Data migration

**Tests:**
- `unittests/tools/test_triage_workflow.py` - New test file for state transitions
- `unittests/auto_triage/test_engine.py` - Update existing tests for new fields

#### Database Indexes Needed

```python
# In Finding model Meta.indexes:
models.Index(fields=["triage_state", "active"]),           # Filter pending active findings
models.Index(fields=["triage_assigned_to", "triage_state"]),  # My assigned findings
models.Index(fields=["triage_due_date"]),                   # SLA tracking
models.Index(fields=["priority_bucket", "triage_state"]),   # Dashboard queries
```

#### State Transition Validation

Valid transitions (enforce in `TriageActionSerializer.validate()` or service layer):
```
pending → escalated, assigned, deferred, dismissed, accepted
escalated → assigned
assigned → deferred, dismissed, accepted
deferred → pending, assigned
dismissed → pending (reopen)
accepted → pending (reopen)
```

#### Permission Considerations

Follow existing pattern from `dojo/authorization/roles_permissions.py`:
- **Finding_View:** Can view triage state and history
- **Finding_Edit:** Can perform triage actions (assign, escalate, defer)
- **Finding_Delete:** Can dismiss findings
- **Product_Manage_Engagement:** Can accept risk (creates Risk_Acceptance record)

#### Integration with Existing Risk Acceptance Flow

The `Risk_Acceptance` model (`dojo/models.py:4728-4777`) is separate from triage workflow:
- When triage_state='accepted', optionally create Risk_Acceptance record
- Risk_Acceptance has richer fields: decision_details, expiration_date, reactivate_expired
- Link via `accepted_findings` ManyToMany relationship
- Triage action 'accept' with reason should offer to create Risk_Acceptance

**Helper Service Pattern:**
```python
# dojo/finding/triage_service.py (NEW FILE)
def perform_triage_action(finding, action, user, reason=None, assigned_to=None, due_date=None):
    """
    Unified triage action handler.

    Validates state transition, updates Finding fields, creates TriageHistory.
    Optionally creates Risk_Acceptance for 'accept' action.
    """
    # Validate transition
    if not is_valid_transition(finding.triage_state, action):
        raise ValidationError(f"Invalid transition from {finding.triage_state} to {action}")

    # Update finding
    old_state = finding.triage_state
    new_state = _action_to_state(action)

    finding.triage_state = new_state
    finding.triage_reason = reason or ''

    if action == 'assign':
        finding.triage_assigned_to = assigned_to
    if action == 'defer':
        finding.triage_due_date = due_date

    finding.save(update_fields=['triage_state', 'triage_reason', 'triage_assigned_to', 'triage_due_date'])

    # Create history record
    TriageHistory.objects.create(
        finding=finding,
        action=action,
        previous_state=old_state,
        new_state=new_state,
        reason=reason,
        performed_by=user,
        performed_at=timezone.now()
    )

    # Optional: Create Risk_Acceptance for 'accept' action
    if action == 'accept':
        # Check if user wants formal risk acceptance
        # This could be a separate API call or query param
        pass

    return finding
```

### Summary of Changes Required

**Phase 2 Deliverables (from success criteria):**

1. ✅ **Add triage workflow fields to Finding model** - Migration 0260
2. ✅ **Add auto-triage tracking fields** - Migration 0260 (auto_triage_rule, auto_triage_confidence)
3. ✅ **Create TriageHistory model** - Migration 0261
4. ✅ **Integrate auto-triage rules with priority scoring** - Update AutoTriageEngine._apply_triage_to_finding()
5. ✅ **Create AutoTriageEngine service** - Already exists, needs updates
6. ✅ **Expose triage actions via REST API** - Add FindingViewSet custom actions
7. ✅ **Unit tests for triage state transitions** - New test file
8. ✅ **Backfill triage_state from existing flags** - Migration 0262

**Integration Dependencies:**

- Phase 1 (priority scoring) is COMPLETE - fields exist, PriorityScorer works
- Phase 2 can leverage priority_score in auto-triage rules (optional enhancement)
- Phase 3 (dashboard) will consume triage_state, priority_bucket, and TriageHistory

## Technical Specification

### Data Model Changes (Finding)
```python
triage_state = models.CharField(max_length=20, choices=[
    ('pending', 'Pending Triage'),
    ('escalated', 'Escalated'),
    ('assigned', 'Assigned'),
    ('deferred', 'Deferred'),
    ('accepted', 'Risk Accepted'),
    ('dismissed', 'Dismissed'),
], default='pending', db_index=True)
triage_assigned_to = models.ForeignKey(Dojo_User, null=True, blank=True, on_delete=models.SET_NULL)
triage_due_date = models.DateField(null=True, blank=True)
triage_reason = models.TextField(blank=True)
auto_triage_rule = models.CharField(max_length=100, blank=True)
auto_triage_confidence = models.IntegerField(null=True, blank=True)
```

### New Model: TriageHistory
- finding (FK)
- action (created, auto_triaged, escalated, assigned, deferred, accepted, dismissed, reopened)
- previous_state, new_state
- reason, rule_name, confidence
- performed_by (FK), performed_at

### API Endpoints
- POST `/api/v2/findings/{id}/triage/` - Perform triage action
- GET `/api/v2/findings/{id}/triage_history/` - Get triage history
- POST `/api/v2/findings/bulk_triage/` - Bulk triage actions

## User Notes

This task depends on Phase 1 (priority scoring) being complete. The triage workflow enables manual and automated vulnerability management.

## Work Log

### 2025-11-25

#### Session 1: Initial Implementation

**Completed:**
- Added triage workflow fields to Finding model (triage_state, triage_assigned_to, triage_due_date, triage_reason, auto_triage_rule, auto_triage_confidence)
- Created TriageHistory model for audit trail tracking
- Implemented triage service layer (dojo/finding/triage_service.py) with:
  - `perform_auto_triage()` - Single finding triage with state management
  - `perform_triage_action()` - Manual triage with validation
  - `bulk_triage()` - Batch triage operations
  - State transition validation logic
- Created REST API endpoints in FindingViewSet:
  - `POST /api/v2/findings/{id}/triage/` - Single finding triage
  - `GET /api/v2/findings/{id}/triage_history/` - Audit trail retrieval
  - `POST /api/v2/findings/bulk_triage/` - Bulk triage operations
- Added serializers: TriageActionSerializer, TriageHistorySerializer, BulkTriageSerializer
- Created database migrations:
  - 0260_finding_triage_workflow_fields.py - Added 6 new fields to Finding
  - 0261_triage_history_model.py - Created TriageHistory model
  - 0262_backfill_triage_state.py - Data migration from legacy flags
- Updated AutoTriageEngine to populate new triage fields and create history records
- Wrote comprehensive unit tests (unittests/test_triage_workflow.py) - 37 test cases

**Code Review Fixes:**
1. **Issue 1: Double-save in AutoTriageEngine** - Added `save` parameter to `perform_auto_triage()` with default `True`. Engine now passes `save=False` and performs single save after updating all fields.
2. **Issue 2: ValidationError.message access pattern** - Changed from `.message` (doesn't exist) to `.messages[0]` (Django's list-based error messages) in both triage_service.py and views.py
3. **Issue 3: Action name inconsistency** - Added `ACTION_TO_HISTORY_ACTION` mapping dictionary to resolve action names ('escalate' → 'escalated', 'accept' → 'accepted', 'assign' → 'assigned', etc.) for consistent history records
4. **Issue 4: Authorization bypass in bulk_triage** - View now filters `finding_ids` through `get_queryset()` before calling `bulk_triage()`, ensuring RBAC enforcement. Added `filtered_count` to response serializer.

**Verification:**
- All fixes validated via Django shell tests
- Django system check passes (no errors)
- State transition logic verified (pending → escalated, assigned → deferred, dismissed → reopened)
- ACTION_TO_HISTORY_ACTION mapping verified for all action types
