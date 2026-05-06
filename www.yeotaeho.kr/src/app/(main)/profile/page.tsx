"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  User,
  Mail,
  LogOut,
  Settings,
  Edit2,
  Save,
  X,
  Camera,
} from "lucide-react";
import { useAuth } from "@/hooks/useStore";
import { getUserName, getUserEmail, getUserId } from "@/utils/tokenStorage";
import {
  getCurrentUser,
  UserInfo,
  getSyncProfile,
  upsertSyncProfile,
  updateUserProfile,
  uploadProfileImage,
} from "@/lib/api/user";

export default function ProfilePage() {
  const router = useRouter();
  const { token, isAuthenticated, logoutAsync } = useAuth();
  const [userName, setUserName] = useState<string | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [profileImage, setProfileImage] = useState<string | null>(null);

  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState<string>("");
  const [editProfileImage, setEditProfileImage] = useState<string>("");
  const [isSaving, setIsSaving] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [targetJob, setTargetJob] = useState<string>("");
  const [interestKeywords, setInterestKeywords] = useState<string[]>([]);
  const [newKeyword, setNewKeyword] = useState<string>("");
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isAuthenticated || !token) {
      router.push("/login");
      return;
    }

    const fetchUserInfo = async () => {
      try {
        const userInfo: UserInfo | null = await getCurrentUser();
        if (userInfo) {
          const displayName = userInfo.nickname || userInfo.name;
          setUserName(displayName || null);
          setUserEmail(userInfo.email || null);
          setUserId(userInfo.id?.toString() || null);
          setProfileImage(userInfo.profileImage || null);
        } else {
          setUserName(getUserName(token));
          setUserEmail(getUserEmail(token));
          setUserId(getUserId(token));
        }

        const syncProfile = await getSyncProfile();
        if (syncProfile) {
          setTargetJob(syncProfile.targetJob || "");
          setInterestKeywords(syncProfile.interestKeywords || []);
        }
      } catch (error) {
        console.error("사용자 정보 조회 실패:", error);
        setUserName(getUserName(token));
        setUserEmail(getUserEmail(token));
        setUserId(getUserId(token));
      }
    };

    fetchUserInfo();
  }, [token, isAuthenticated, router]);

  const handleEdit = () => {
    setEditName(userName || "");
    setEditProfileImage(profileImage || "");
    setSelectedFile(null);
    setPreviewUrl(null);
    setIsEditing(true);
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      if (!file.type.startsWith("image/")) {
        alert("이미지 파일만 업로드 가능합니다.");
        return;
      }
      if (file.size > 5 * 1024 * 1024) {
        alert("파일 크기는 5MB 이하여야 합니다.");
        return;
      }
      setSelectedFile(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setPreviewUrl(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleAvatarClick = () => {
    if (isEditing && fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditName(userName || "");
    setEditProfileImage(profileImage || "");
    setSelectedFile(null);
    setPreviewUrl(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleSave = async () => {
    if (isSaving) return;
    setIsSaving(true);
    try {
      let imageUrl = editProfileImage.trim() || undefined;
      if (selectedFile) {
        const uploadedUrl = await uploadProfileImage(selectedFile);
        if (uploadedUrl) {
          imageUrl = uploadedUrl;
        } else {
          alert("이미지 업로드에 실패했습니다.");
          setIsSaving(false);
          return;
        }
      }
      const updateData = {
        name: editName.trim() || undefined,
        profileImage: imageUrl,
      };
      const updatedUser = await updateUserProfile(updateData);
      const updatedSyncProfile = await upsertSyncProfile({
        targetJob: targetJob.trim() || null,
        interestKeywords,
      });

      if (updatedUser && updatedSyncProfile) {
        const displayName = updatedUser.nickname || updatedUser.name;
        setUserName(displayName || null);
        setProfileImage(updatedUser.profileImage || null);
        setTargetJob(updatedSyncProfile.targetJob || "");
        setInterestKeywords(updatedSyncProfile.interestKeywords || []);
        setSelectedFile(null);
        setPreviewUrl(null);
        setIsEditing(false);
        alert("프로필이 업데이트되었습니다.");
      } else {
        alert("프로필 업데이트에 실패했습니다.");
      }
    } catch (error) {
      console.error("[프로필 저장 오류]", error);
      alert("프로필 업데이트 중 오류가 발생했습니다.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleAddKeyword = () => {
    const value = newKeyword.trim();
    if (!value || interestKeywords.includes(value)) return;
    setInterestKeywords((prev) => [...prev, value]);
    setNewKeyword("");
  };

  const handleRemoveKeyword = (keyword: string) => {
    setInterestKeywords((prev) => prev.filter((item) => item !== keyword));
  };

  const handleLogout = async () => {
    try {
      await logoutAsync();
    } catch (error) {
      console.error("로그아웃 처리 중 오류:", error);
    } finally {
      router.push("/");
      router.refresh();
    }
  };

  if (!isAuthenticated || !token) {
    return null;
  }

  return (
    <div className="max-w-4xl mx-auto w-full">
      <div className="flex items-center gap-3 mb-6">
        <Link
          href="/"
          className="p-2 text-gray-600 hover:text-red-600 transition rounded-full hover:bg-gray-100"
          aria-label="홈으로"
        >
          <ArrowLeft size={20} />
        </Link>
        <h1 className="text-xl font-bold text-gray-800">프로필</h1>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden mb-6">
        <div className="bg-gradient-to-r from-red-600 to-red-700 px-6 py-12">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-6">
              <div className="relative">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                {previewUrl ? (
                  <img
                    src={previewUrl}
                    alt="Profile Preview"
                    className="w-24 h-24 rounded-full object-cover shadow-lg border-4 border-white cursor-pointer"
                    onClick={handleAvatarClick}
                  />
                ) : profileImage ? (
                  <img
                    src={profileImage}
                    alt="Profile"
                    className={`w-24 h-24 rounded-full object-cover shadow-lg border-4 border-white ${
                      isEditing ? "cursor-pointer hover:opacity-80" : ""
                    }`}
                    onClick={handleAvatarClick}
                    onError={(e) => {
                      e.currentTarget.style.display = "none";
                      const parent = e.currentTarget.parentElement;
                      if (parent) {
                        const fallback = parent.querySelector(".avatar-fallback");
                        if (fallback) fallback.classList.remove("hidden");
                      }
                    }}
                  />
                ) : null}
                <div
                  className={`w-24 h-24 bg-white rounded-full flex items-center justify-center shadow-lg ${
                    previewUrl || profileImage ? "hidden avatar-fallback" : ""
                  } ${isEditing ? "cursor-pointer hover:bg-gray-100" : ""}`}
                  onClick={handleAvatarClick}
                >
                  <User size={48} className="text-red-600" />
                </div>
                {isEditing && (
                  <div
                    className="absolute bottom-0 right-0 bg-white rounded-full p-2 shadow-lg cursor-pointer hover:bg-gray-100"
                    onClick={handleAvatarClick}
                    title="프로필 사진 변경"
                  >
                    <Camera size={16} className="text-red-600" />
                  </div>
                )}
              </div>
              <div className="text-white">
                {isEditing ? (
                  <div className="space-y-2">
                    <input
                      type="text"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      placeholder="이름을 입력하세요"
                      className="bg-white/20 text-white text-2xl font-bold px-3 py-1 rounded border border-white/30 focus:outline-none focus:ring-2 focus:ring-white/50 placeholder:text-white/60"
                      maxLength={50}
                    />
                    {selectedFile && (
                      <p className="text-white/80 text-xs">
                        선택된 파일: {selectedFile.name}
                      </p>
                    )}
                  </div>
                ) : (
                  <>
                    <h2 className="text-2xl font-bold mb-1">
                      {userName || "사용자"}
                    </h2>
                    <p className="text-red-100 text-sm">
                      {userEmail || "이메일 정보 없음"}
                    </p>
                  </>
                )}
              </div>
            </div>
            {!isEditing ? (
              <button
                onClick={handleEdit}
                className="text-white hover:text-red-100 transition p-2 rounded-full hover:bg-white/20"
                title="프로필 편집"
                type="button"
              >
                <Edit2 size={20} />
              </button>
            ) : (
              <div className="flex items-center space-x-2">
                <button
                  onClick={handleSave}
                  disabled={isSaving}
                  className="text-white hover:text-red-100 transition p-2 rounded-full hover:bg-white/20 disabled:opacity-50"
                  title="저장"
                  type="button"
                >
                  <Save size={20} />
                </button>
                <button
                  onClick={handleCancel}
                  disabled={isSaving}
                  className="text-white hover:text-red-100 transition p-2 rounded-full hover:bg-white/20 disabled:opacity-50"
                  title="취소"
                  type="button"
                >
                  <X size={20} />
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="p-6 space-y-6">
          <div className="flex items-center space-x-4 pb-4 border-b border-gray-200">
            <div className="w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center">
              <User size={20} className="text-gray-600" />
            </div>
            <div className="flex-1">
              <p className="text-sm text-gray-500 mb-1">사용자 ID</p>
              <p className="text-gray-800 font-medium">
                {userId || "ID 정보 없음"}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-4 pb-4 border-b border-gray-200">
            <div className="w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center">
              <Mail size={20} className="text-gray-600" />
            </div>
            <div className="flex-1">
              <p className="text-sm text-gray-500 mb-1">이메일</p>
              <p className="text-gray-800 font-medium">
                {userEmail || "이메일 정보 없음"}
              </p>
            </div>
          </div>

          <div className="pt-4 space-y-3">
            <div className="rounded-lg border border-gray-200 p-4 bg-gray-50">
              <p className="text-sm text-gray-500 mb-1">목표 직무</p>
              {isEditing ? (
                <input
                  type="text"
                  value={targetJob}
                  onChange={(e) => setTargetJob(e.target.value)}
                  placeholder="예) 백엔드 엔지니어"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-red-500"
                />
              ) : (
                <p className="text-gray-800 font-medium">
                  {targetJob || "아직 설정되지 않았습니다."}
                </p>
              )}
            </div>

            <div className="rounded-lg border border-gray-200 p-4 bg-gray-50">
              <p className="text-sm text-gray-500 mb-2">관심 키워드</p>
              <div className="flex flex-wrap gap-2 mb-3">
                {interestKeywords.length > 0 ? (
                  interestKeywords.map((keyword) => (
                    <span
                      key={keyword}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-white border border-gray-300 text-sm text-gray-700"
                    >
                      {keyword}
                      {isEditing && (
                        <button
                          type="button"
                          onClick={() => handleRemoveKeyword(keyword)}
                          className="text-gray-500 hover:text-red-600"
                        >
                          ×
                        </button>
                      )}
                    </span>
                  ))
                ) : (
                  <p className="text-sm text-gray-500">
                    아직 등록된 키워드가 없습니다.
                  </p>
                )}
              </div>

              {isEditing && (
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newKeyword}
                    onChange={(e) => setNewKeyword(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        handleAddKeyword();
                      }
                    }}
                    placeholder="키워드 추가"
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-red-500"
                  />
                  <button
                    type="button"
                    onClick={handleAddKeyword}
                    className="px-3 py-2 rounded-md bg-red-600 text-white hover:bg-red-700"
                  >
                    추가
                  </button>
                </div>
              )}
            </div>

            <button
              type="button"
              className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition font-medium"
            >
              <Settings size={20} />
              <span>설정</span>
            </button>
            <button
              type="button"
              onClick={handleLogout}
              className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition font-medium"
            >
              <LogOut size={20} />
              <span>로그아웃</span>
            </button>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-bold text-gray-800 mb-4">계정 정보</h3>
        <div className="space-y-3 text-sm text-gray-600">
          <p>계정 관리를 위해 필요한 정보입니다.</p>
          <p className="text-xs text-gray-500">
            추가 기능은 추후 업데이트 예정입니다.
          </p>
        </div>
      </div>
    </div>
  );
}
