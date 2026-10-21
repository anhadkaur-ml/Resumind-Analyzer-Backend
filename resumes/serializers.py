from pathlib import Path

from django.core.files.base import ContentFile
from rest_framework import serializers

from .analysis import analyze_resume, extract_resume_text
from .models import BuilderResume, CareerConversation, CareerMessage, ChatMessage, ResumeAnalysis, ResumeVersion
from accounts.models import Notification
from accounts.email_service import send_analysis_ready_email, send_builder_completed_email


class AskAIRequestSerializer(serializers.Serializer):
    # The employee's question for the AI coach.
    question = serializers.CharField(max_length=2000, trim_whitespace=True)

    # Identifies the exact analysis report currently open in the frontend.
    # The view also checks that this report belongs to the logged-in employee.
    analysis_id = serializers.IntegerField(min_value=1)


class CareerCopilotRequestSerializer(serializers.Serializer):
    """Validate a question and optionally identify an existing owned conversation."""

    question = serializers.CharField(max_length=2000, trim_whitespace=True)
    conversation_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)


class ProfessionalSummaryRequestSerializer(serializers.Serializer):
    """Validate the Resume Builder facts used to generate a profile summary."""

    target_role = serializers.CharField(max_length=180, required=False, allow_blank=True)
    skills = serializers.ListField(child=serializers.CharField(max_length=100), required=False)
    experience = serializers.CharField(max_length=6000, required=False, allow_blank=True)
    projects = serializers.CharField(max_length=6000, required=False, allow_blank=True)
    current_summary = serializers.CharField(max_length=3000, required=False, allow_blank=True)

    def validate(self, attrs):
        if not any((attrs.get("target_role"), attrs.get("skills"), attrs.get("experience"), attrs.get("projects"), attrs.get("current_summary"))):
            raise serializers.ValidationError("Add a target role, skill, experience, project, or rough summary first.")
        return attrs


class JobDescriptionRequestSerializer(serializers.Serializer):
    """Validate the target used to draft a job description."""

    target_role = serializers.CharField(max_length=180, trim_whitespace=True)
    target_company = serializers.CharField(max_length=180, required=False, allow_blank=True, trim_whitespace=True)


class TailorResumeRequestSerializer(serializers.Serializer):
    """Validate candidate facts and the job description used for tailoring."""

    target_role = serializers.CharField(max_length=180, trim_whitespace=True)
    target_company = serializers.CharField(max_length=180, required=False, allow_blank=True, trim_whitespace=True)
    job_description = serializers.CharField(max_length=12000, trim_whitespace=True)
    summary = serializers.CharField(max_length=3000, required=False, allow_blank=True)
    skills = serializers.ListField(child=serializers.CharField(max_length=100), required=False)
    experience = serializers.CharField(max_length=8000, required=False, allow_blank=True)
    projects = serializers.CharField(max_length=8000, required=False, allow_blank=True)

    def validate(self, attrs):
        if not any((attrs.get("summary"), attrs.get("skills"), attrs.get("experience"), attrs.get("projects"))):
            raise serializers.ValidationError("Add a summary, skill, experience, or project before tailoring the resume.")
        return attrs



class ChatMessageSerializer(serializers.ModelSerializer):
    """Read-only message format used when restoring report chat history."""

    class Meta:
        model = ChatMessage
        # Clients can load messages, but messages are created only by AskAIView.
        fields = ("id", "role", "content", "created_at")
        read_only_fields = fields


class CareerMessageSerializer(serializers.ModelSerializer):
    """Read-only Career Copilot message returned when reopening a conversation."""

    class Meta:
        model = CareerMessage
        fields = ("id", "role", "content", "created_at")
        read_only_fields = fields


class CareerConversationSerializer(serializers.ModelSerializer):
    """Return conversation metadata together with its ordered messages."""

    messages = CareerMessageSerializer(many=True, read_only=True)

    class Meta:
        model = CareerConversation
        fields = ("id", "title", "messages", "created_at", "updated_at")
        # Only the title can be edited; ownership and messages are server-managed.
        read_only_fields = ("id", "messages", "created_at", "updated_at")

    def validate_title(self, value):
        title = value.strip()
        if not title:
            raise serializers.ValidationError("Conversation title cannot be empty.")
        return title


class ResumeAnalysisSerializer(serializers.ModelSerializer):
    """Read-only representation used by history and report-detail APIs."""

    class Meta:
        model = ResumeAnalysis
        fields = ("id", "original_filename", "job_title", "job_description", "overall_score", "impact_score", "clarity_score", "ats_score", "status", "recommendations", "detailed_report", "created_at")
        read_only_fields = fields


class ResumeAnalysisCreateSerializer(serializers.ModelSerializer):
    """Validate an upload, run analysis, and save the resulting report."""

    # The API accepts the friendly key `resume` and maps it to the model field.
    resume = serializers.FileField(write_only=True, source="resume_file")

    class Meta:
        model = ResumeAnalysis
        fields = ("resume", "job_title", "job_description")

    def validate_resume(self, upload):
        # Reject unsupported or oversized files before parsing or calling AI.
        if Path(upload.name).suffix.lower() not in {".pdf", ".doc", ".docx"}:
            raise serializers.ValidationError("Upload a PDF, DOC, or DOCX resume.")
        if upload.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("The resume must be 10 MB or smaller.")
        return upload

    def create(self, validated_data):
        upload = validated_data["resume_file"]
        # Extract text once, generate scores/report, then persist both the
        # original file and structured analysis under the current employee.
        scores = analyze_resume(extract_resume_text(upload), validated_data["job_title"], validated_data.get("job_description", ""))
        analysis = ResumeAnalysis.objects.create(user=self.context["request"].user, original_filename=upload.name, **validated_data, **scores)
        # Notify the employee only after the saved report has a usable ID/link.
        Notification.objects.create(
            user=analysis.user,
            title="Resume analysis ready",
            message=f"{analysis.original_filename} scored {analysis.overall_score}/100 for {analysis.job_title}.",
            kind="resume_analysis",
            link=f"/employee/reports/{analysis.id}",
        )
        send_analysis_ready_email(analysis)
        return analysis


class BuilderResumeAnalysisSerializer(serializers.Serializer):
    """Analyze a saved Builder resume without asking the user to upload it again."""

    job_title = serializers.CharField(max_length=180, trim_whitespace=True)
    job_description = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)

    @staticmethod
    def builder_text(builder):
        """Convert all editable Builder sections into readable analysis text."""

        education = "\n".join(
            " | ".join(str(entry.get(key, "")).strip() for key in ("education_type", "degree", "field", "institution", "start_year", "end_year") if str(entry.get(key, "")).strip())
            for entry in builder.education_entries if isinstance(entry, dict)
        ) or builder.education
        skills = ", ".join(builder.skill_items) or builder.skills
        projects = "\n".join(
            " | ".join(str(entry.get(key, "")).strip() for key in ("name", "technologies", "description", "link") if str(entry.get(key, "")).strip())
            for entry in builder.project_entries if isinstance(entry, dict)
        ) or builder.projects
        return "\n\n".join(filter(None, (
            builder.full_name,
            f"Target role: {builder.target_role}",
            f"Target company: {builder.target_company}" if builder.target_company else "",
            f"Target job description:\n{builder.job_description}" if builder.job_description else "",
            f"Contact: {builder.email} {builder.phone} {builder.location}",
            f"Professional Summary\n{builder.summary}",
            f"Experience\n{builder.job_title} | {builder.company} | {builder.period}\n{builder.experience}",
            f"Education\n{education}",
            f"Skills\n{skills}",
            f"Projects\n{projects}",
        )))

    def create(self, validated_data):
        builder = self.context["builder"]
        text = self.builder_text(builder)
        if not text.strip():
            raise serializers.ValidationError("Add resume information before starting an analysis.")
        scores = analyze_resume(text, validated_data["job_title"], validated_data.get("job_description", ""))
        safe_title = "".join(character if character.isalnum() or character in "-_" else "_" for character in builder.title).strip("_") or "builder_resume"
        document = ContentFile(text.encode("utf-8"), name=f"{safe_title}.txt")
        analysis = ResumeAnalysis.objects.create(
            user=self.context["request"].user,
            resume_file=document,
            original_filename=document.name,
            **validated_data,
            **scores,
        )
        Notification.objects.create(
            user=analysis.user,
            title="Resume analysis ready",
            message=f"{builder.title} scored {analysis.overall_score}/100 for {analysis.job_title}.",
            kind="resume_analysis",
            link=f"/employee/reports/{analysis.id}",
        )
        send_analysis_ready_email(analysis)
        return analysis


class ResumeVersionSerializer(serializers.ModelSerializer):
    """Represent and update metadata for an already uploaded resume version."""

    class Meta:
        model = ResumeVersion
        fields = ("id", "original_filename", "title", "target_role", "category", "score", "is_archived", "created_at", "updated_at")
        read_only_fields = ("id", "original_filename", "created_at", "updated_at")


class ResumeVersionCreateSerializer(serializers.ModelSerializer):
    """Validate and save a reusable resume version for the current employee."""

    resume = serializers.FileField(write_only=True, source="resume_file")

    class Meta:
        model = ResumeVersion
        fields = ("resume", "title", "target_role", "category")

    def validate_resume(self, upload):
        if Path(upload.name).suffix.lower() not in {".pdf", ".doc", ".docx"}:
            raise serializers.ValidationError("Upload a PDF, DOC, or DOCX resume.")
        if upload.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("The resume must be 10 MB or smaller.")
        return upload

    def create(self, validated_data):
        upload = validated_data["resume_file"]
        return ResumeVersion.objects.create(user=self.context["request"].user, original_filename=upload.name, **validated_data)


class BuilderResumeSerializer(serializers.ModelSerializer):
    """Validate and persist editable Resume Builder content."""

    class Meta:
        model = BuilderResume
        fields = (
            "id", "title", "target_role", "target_company", "job_description", "template", "status", "completion",
            "full_name", "email", "phone", "location", "summary", "job_title",
            "company", "period", "experience", "education", "skills", "projects",
            "education_entries", "skill_items", "project_entries",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "completion", "created_at", "updated_at")

    def validate(self, attrs):
        # A completed resume needs the minimum identity and targeting fields;
        # drafts deliberately allow incomplete data.
        status_value = attrs.get("status", getattr(self.instance, "status", BuilderResume.Status.DRAFT))
        if status_value == BuilderResume.Status.COMPLETED:
            required = ("full_name", "email", "target_role")
            missing = [field for field in required if not attrs.get(field, getattr(self.instance, field, ""))]
            if missing:
                raise serializers.ValidationError({field: "This field is required to generate a resume." for field in missing})
        return attrs

    def validate_education_entries(self, entries):
        """Accept only compact education objects with supported text fields."""

        allowed = ("education_type", "degree", "field", "institution", "start_year", "end_year")
        if not isinstance(entries, list) or len(entries) > 20:
            raise serializers.ValidationError("Provide a list containing no more than 20 education records.")
        return [
            {key: str(entry.get(key, "")).strip()[:250] for key in allowed}
            for entry in entries
            if isinstance(entry, dict)
        ]

    def validate_skill_items(self, skills):
        """Normalize skill tags and remove blank or duplicate values."""

        if not isinstance(skills, list) or len(skills) > 100:
            raise serializers.ValidationError("Provide a list containing no more than 100 skills.")
        normalized = []
        for skill in skills:
            value = str(skill).strip()[:100]
            if value and value.casefold() not in {item.casefold() for item in normalized}:
                normalized.append(value)
        return normalized

    def validate_project_entries(self, entries):
        """Keep each added project in a predictable, safe structure."""

        allowed = ("name", "technologies", "description", "link")
        if not isinstance(entries, list) or len(entries) > 30:
            raise serializers.ValidationError("Provide a list containing no more than 30 projects.")
        return [
            {key: str(entry.get(key, "")).strip()[:3000 if key == "description" else 500] for key in allowed}
            for entry in entries
            if isinstance(entry, dict)
        ]

    def _completion(self, values):
        # Completion is calculated by the server so clients cannot store an
        # incorrect percentage. Status becomes Completed only at 100 percent.
        # Work-experience fields are optional and therefore do not reduce a
        # draft's completion percentage when the user leaves them empty.
        fields = (
            "title", "target_role", "full_name", "email", "summary",
        )
        filled = sum(bool(str(values.get(field, "")).strip()) for field in fields)
        # Either structured values or legacy text count as completed sections.
        filled += bool(values.get("education_entries") or str(values.get("education", "")).strip())
        filled += bool(values.get("skill_items") or str(values.get("skills", "")).strip())
        filled += bool(values.get("project_entries") or str(values.get("projects", "")).strip())
        return round(filled / (len(fields) + 3) * 100)

    def create(self, validated_data):
        values = {**validated_data}
        values["completion"] = 100 if values.get("status") == BuilderResume.Status.COMPLETED else self._completion(values)
        resume = BuilderResume.objects.create(user=self.context["request"].user, **values)
        if resume.status == BuilderResume.Status.COMPLETED:
            send_builder_completed_email(resume)
        return resume

    def update(self, instance, validated_data):
        previous_status = instance.status
        merged = {field: validated_data.get(field, getattr(instance, field)) for field in self.Meta.fields if hasattr(instance, field)}
        validated_data["completion"] = 100 if merged["status"] == BuilderResume.Status.COMPLETED else self._completion(merged)
        resume = super().update(instance, validated_data)
        if previous_status != BuilderResume.Status.COMPLETED and resume.status == BuilderResume.Status.COMPLETED:
            send_builder_completed_email(resume)
        return resume
