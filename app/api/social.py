import random
import string

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth import get_current_user
from db.models import Assignment, Community, CommunityPost, StudyGroup, User
from db.sessions import getDb
from services.notification_service import reconcile_assignment_completion_notifications

router = APIRouter(prefix="/social", tags=["Study Groups and Communities"])


def _generate_code(prefix: str = "QZ") -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"{prefix}-{suffix}"


class CreateGroupPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)


class JoinGroupPayload(BaseModel):
    code: str = Field(..., min_length=6)


class CreateCommunityPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = None


class CreatePostPayload(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


def _serialize_group(group: StudyGroup) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "code": group.uniqueGroupCode,
        "creatorId": group.creatorId,
        "createdAt": group.createdAt.isoformat() if group.createdAt else None,
        "memberCount": len(group.members or []),
        "members": [
            {"id": member.id, "fullName": member.fullName, "email": member.email}
            for member in (group.members or [])
        ],
    }


def _serialize_community(community: Community) -> dict:
    return {
        "id": community.id,
        "name": community.name,
        "description": community.description,
        "creatorId": community.creatorId,
        "createdAt": community.createdAt.isoformat() if community.createdAt else None,
        "memberCount": len(community.members or []),
        "members": [
            {"id": member.id, "fullName": member.fullName, "email": member.email}
            for member in (community.members or [])
        ],
    }


def _serialize_post(post: CommunityPost) -> dict:
    return {
        "id": post.id,
        "communityId": post.communityId,
        "authorId": post.authorId,
        "authorName": post.author.fullName if post.author else "Unknown",
        "content": post.content,
        "createdAt": post.createdAt.isoformat() if post.createdAt else None,
    }


@router.get("/groups")
def list_user_groups(
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["userId"]
    groups = (
        db.query(StudyGroup)
        .filter((StudyGroup.creatorId == user_id) | (StudyGroup.members.any(User.id == user_id)))
        .order_by(StudyGroup.createdAt.desc())
        .all()
    )
    return {"groups": [_serialize_group(group) for group in groups]}


@router.post("/groups/create")
def create_group(
    payload: CreateGroupPayload,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group name is required.")

    code = _generate_code()
    while db.query(StudyGroup).filter(StudyGroup.uniqueGroupCode == code).first():
        code = _generate_code()

    user = db.query(User).filter(User.id == current_user["userId"]).first()
    group = StudyGroup(name=name, uniqueGroupCode=code, creatorId=current_user["userId"])
    db.add(group)
    db.flush()
    if user is not None and user not in group.members:
        group.members.append(user)
    db.commit()
    db.refresh(group)
    return {"message": "Study group created.", "group": _serialize_group(group)}


@router.post("/groups/join")
def join_group(
    payload: JoinGroupPayload,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    group = db.query(StudyGroup).filter(StudyGroup.uniqueGroupCode == payload.code.strip().upper()).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group code not found.")

    user = db.query(User).filter(User.id == current_user["userId"]).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    if user in group.members:
        return {"message": "You are already a member of this group.", "group": _serialize_group(group)}

    group.members.append(user)
    db.flush()
    assignments = (
        db.query(Assignment)
        .filter(Assignment.targetGroups.any(StudyGroup.id == group.id))
        .all()
    )
    for assignment in assignments:
        reconcile_assignment_completion_notifications(db, assignment)
    db.commit()
    return {"message": "Joined study group.", "group": _serialize_group(group)}


@router.post("/groups/{group_id}/invite")
def invite_group_members(
    group_id: int,
    payload: dict,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    group = db.query(StudyGroup).filter(StudyGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")
    if group.creatorId != current_user["userId"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the group creator can invite members.")

    email = str(payload.get("email", "")).strip().lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required to invite a student.")
    return {"message": "Invite prepared.", "inviteEmail": email, "groupCode": group.uniqueGroupCode}


@router.get("/communities")
def list_communities(
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    communities = (
        db.query(Community)
        .filter((Community.creatorId == current_user["userId"]) | (Community.members.any(User.id == current_user["userId"])))
        .order_by(Community.createdAt.desc())
        .all()
    )
    return {"communities": [_serialize_community(community) for community in communities]}


@router.post("/communities/create")
def create_community(
    payload: CreateCommunityPayload,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    name = payload.name.strip()
    description = (payload.description or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Community name is required.")

    community = Community(name=name, description=description or None, creatorId=current_user["userId"])
    db.add(community)
    db.flush()
    user = db.query(User).filter(User.id == current_user["userId"]).first()
    if user is not None and user not in community.members:
        community.members.append(user)
    db.commit()
    db.refresh(community)
    return {"message": "Community created.", "community": _serialize_community(community)}


@router.post("/communities/{community_id}/join")
def join_community(
    community_id: int,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Community not found.")

    user = db.query(User).filter(User.id == current_user["userId"]).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    if user in community.members:
        return {"message": "Already a member.", "community": _serialize_community(community)}

    community.members.append(user)
    db.commit()
    return {"message": "Joined community.", "community": _serialize_community(community)}


@router.get("/communities/{community_id}/posts")
def get_community_posts(
    community_id: int,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Community not found.")
    if current_user["userId"] not in [member.id for member in (community.members or [])]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You need to join the community to read its posts.")

    posts = db.query(CommunityPost).filter(CommunityPost.communityId == community_id).order_by(CommunityPost.createdAt.desc()).all()
    return {"community": _serialize_community(community), "posts": [_serialize_post(post) for post in posts]}


@router.post("/communities/{community_id}/posts")
def create_community_post(
    community_id: int,
    payload: CreatePostPayload,
    db: Session = Depends(getDb),
    current_user: dict = Depends(get_current_user),
):
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Community not found.")
    if current_user["userId"] not in [member.id for member in (community.members or [])]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You need to join the community before posting.")

    post = CommunityPost(
        communityId=community_id,
        authorId=current_user["userId"],
        content=payload.content.strip(),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return {"message": "Post published.", "post": _serialize_post(post)}
