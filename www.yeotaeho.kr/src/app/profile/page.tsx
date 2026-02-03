"use client";

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowLeft, User, Mail, LogOut, Settings, Edit2, Save, X, Camera } from 'lucide-react';
import { useAuth } from '@/hooks/useStore';
import { getUserName, getUserEmail, getUserId } from '@/utils/tokenStorage';
import { getCurrentUser, UserInfo, updateUserProfile, uploadProfileImage } from '@/lib/api/user';

export default function ProfilePage() {
    const router = useRouter();
    const { token, isAuthenticated, logoutAsync } = useAuth();
    const [userName, setUserName] = useState<string | null>(null);
    const [userNickname, setUserNickname] = useState<string | null>(null);
    const [userEmail, setUserEmail] = useState<string | null>(null);
    const [userId, setUserId] = useState<string | null>(null);
    const [profileImage, setProfileImage] = useState<string | null>(null);

    // 편집 모드 상태
    const [isEditing, setIsEditing] = useState(false);
    const [editName, setEditName] = useState<string>('');
    const [editProfileImage, setEditProfileImage] = useState<string>('');
    const [isSaving, setIsSaving] = useState(false);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const fileInputRef = React.useRef<HTMLInputElement>(null);

    useEffect(() => {
        // 로그인되지 않은 경우 홈으로 리다이렉트
        if (!isAuthenticated || !token) {
            router.push('/login');
            return;
        }

        // DB에서 사용자 정보 가져오기
        const fetchUserInfo = async () => {
            try {
                const userInfo: UserInfo | null = await getCurrentUser();
                if (userInfo) {
                    // DB에서 가져온 정보 사용
                    // 표시명: nickname이 있으면 nickname, 없으면 name
                    const displayName = userInfo.nickname || userInfo.name;
                    setUserName(displayName || null);
                    setUserNickname(userInfo.nickname || null);
                    setUserEmail(userInfo.email || null);
                    setUserId(userInfo.id?.toString() || null);
                    setProfileImage(userInfo.profileImage || null);
                } else {
                    // API 실패 시 JWT에서 가져오기 (fallback)
                    const name = getUserName(token);
                    const email = getUserEmail(token);
                    const id = getUserId(token);
                    setUserName(name);
                    setUserEmail(email);
                    setUserId(id);
                }
            } catch (error) {
                console.error('사용자 정보 조회 실패:', error);
                // API 실패 시 JWT에서 가져오기 (fallback)
                const name = getUserName(token);
                const email = getUserEmail(token);
                const id = getUserId(token);
                setUserName(name);
                setUserEmail(email);
                setUserId(id);
            }
        };

        fetchUserInfo();
    }, [token, isAuthenticated, router]);

    // 편집 모드 시작
    const handleEdit = () => {
        setEditName(userName || '');
        setEditProfileImage(profileImage || '');
        setSelectedFile(null);
        setPreviewUrl(null);
        setIsEditing(true);
    };

    // 파일 선택 핸들러
    const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (file) {
            // 파일 타입 검증
            if (!file.type.startsWith('image/')) {
                alert('이미지 파일만 업로드 가능합니다.');
                return;
            }

            // 파일 크기 검증 (5MB)
            if (file.size > 5 * 1024 * 1024) {
                alert('파일 크기는 5MB 이하여야 합니다.');
                return;
            }

            setSelectedFile(file);

            // 미리보기 URL 생성
            const reader = new FileReader();
            reader.onloadend = () => {
                setPreviewUrl(reader.result as string);
            };
            reader.readAsDataURL(file);
        }
    };

    // 아바타 클릭 핸들러
    const handleAvatarClick = () => {
        if (isEditing && fileInputRef.current) {
            fileInputRef.current.click();
        }
    };

    // 편집 취소
    const handleCancel = () => {
        setIsEditing(false);
        setEditName(userName || '');
        setEditProfileImage(profileImage || '');
        setSelectedFile(null);
        setPreviewUrl(null);
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    // 프로필 저장
    const handleSave = async () => {
        if (isSaving) return;

        setIsSaving(true);
        try {
            console.log('[프로필 저장 시작] 사용자가 저장 버튼을 클릭했습니다.');
            console.log('[프로필 저장] 입력된 이름:', editName);

            let imageUrl = editProfileImage.trim() || undefined;

            // 파일이 선택된 경우 먼저 업로드
            if (selectedFile) {
                console.log('[프로필 저장] 이미지 파일 업로드 시작:', selectedFile.name);
                const uploadedUrl = await uploadProfileImage(selectedFile);
                if (uploadedUrl) {
                    imageUrl = uploadedUrl;
                    console.log('[프로필 저장] 이미지 파일 업로드 완료:', uploadedUrl);
                } else {
                    console.error('[프로필 저장] 이미지 업로드 실패');
                    alert('이미지 업로드에 실패했습니다.');
                    setIsSaving(false);
                    return;
                }
            }

            // 프로필 정보 업데이트
            const updateData = {
                name: editName.trim() || undefined,
                profileImage: imageUrl,
            };
            console.log('[프로필 저장] 서버 API 호출 시작 - 전송 데이터:', updateData);

            const updatedUser = await updateUserProfile(updateData);

            if (updatedUser) {
                console.log('[프로필 저장] 서버 API 응답 수신:', updatedUser);
                console.log('[프로필 저장] DB 저장된 nickname:', updatedUser.nickname);
                console.log('[프로필 저장] DB 저장된 name:', updatedUser.name);

                // 표시명: nickname이 있으면 nickname, 없으면 name
                const displayName = updatedUser.nickname || updatedUser.name;
                setUserName(displayName || null);
                setUserNickname(updatedUser.nickname || null);
                setProfileImage(updatedUser.profileImage || null);
                setSelectedFile(null);
                setPreviewUrl(null);
                setIsEditing(false);

                console.log('[프로필 저장 완료] 화면 업데이트 완료, 표시명:', displayName);
                alert('프로필이 업데이트되었습니다.');
            } else {
                console.error('[프로필 저장 실패] 서버 응답이 null입니다.');
                alert('프로필 업데이트에 실패했습니다.');
            }
        } catch (error) {
            console.error('[프로필 저장 오류]', error);
            alert('프로필 업데이트 중 오류가 발생했습니다.');
        } finally {
            setIsSaving(false);
        }
    };

    // 로그아웃 핸들러
    const handleLogout = async () => {
        try {
            await logoutAsync();
        } catch (error) {
            console.error('로그아웃 처리 중 오류:', error);
        } finally {
            router.push('/');
            router.refresh();
        }
    };

    // 로딩 상태 또는 미인증 상태
    if (!isAuthenticated || !token) {
        return null; // 리다이렉트 중
    }

    return (
        <div className="min-h-screen bg-gray-50">
            {/* Header */}
            <header className="bg-white shadow-sm border-b border-gray-200">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
                    <div className="flex items-center space-x-4">
                        <Link
                            href="/"
                            className="p-2 text-gray-600 hover:text-red-600 transition rounded-full hover:bg-gray-100"
                        >
                            <ArrowLeft size={20} />
                        </Link>
                        <h1 className="text-xl font-bold text-gray-800">프로필</h1>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Profile Card */}
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden mb-6">
                    {/* Profile Header */}
                    <div className="bg-gradient-to-r from-red-600 to-red-700 px-6 py-12">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-6">
                                {/* Avatar */}
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
                                            className={`w-24 h-24 rounded-full object-cover shadow-lg border-4 border-white ${isEditing ? 'cursor-pointer hover:opacity-80' : ''}`}
                                            onClick={handleAvatarClick}
                                            onError={(e) => {
                                                // 이미지 로드 실패 시 기본 아이콘 표시
                                                e.currentTarget.style.display = 'none';
                                                const parent = e.currentTarget.parentElement;
                                                if (parent) {
                                                    const fallback = parent.querySelector('.avatar-fallback');
                                                    if (fallback) fallback.classList.remove('hidden');
                                                }
                                            }}
                                        />
                                    ) : null}
                                    <div className={`w-24 h-24 bg-white rounded-full flex items-center justify-center shadow-lg ${(previewUrl || profileImage) ? 'hidden avatar-fallback' : ''} ${isEditing ? 'cursor-pointer hover:bg-gray-100' : ''}`}
                                        onClick={handleAvatarClick}>
                                        <User size={48} className="text-red-600" />
                                    </div>
                                    {isEditing && (
                                        <div className="absolute bottom-0 right-0 bg-white rounded-full p-2 shadow-lg cursor-pointer hover:bg-gray-100"
                                            onClick={handleAvatarClick}
                                            title="프로필 사진 변경">
                                            <Camera size={16} className="text-red-600" />
                                        </div>
                                    )}
                                </div>
                                {/* User Info */}
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
                                                {userName || '사용자'}
                                            </h2>
                                            <p className="text-red-100 text-sm">
                                                {userEmail || '이메일 정보 없음'}
                                            </p>
                                        </>
                                    )}
                                </div>
                            </div>
                            {/* Edit Button */}
                            {!isEditing ? (
                                <button
                                    onClick={handleEdit}
                                    className="text-white hover:text-red-100 transition p-2 rounded-full hover:bg-white/20"
                                    title="프로필 편집"
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
                                    >
                                        <Save size={20} />
                                    </button>
                                    <button
                                        onClick={handleCancel}
                                        disabled={isSaving}
                                        className="text-white hover:text-red-100 transition p-2 rounded-full hover:bg-white/20 disabled:opacity-50"
                                        title="취소"
                                    >
                                        <X size={20} />
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Profile Details */}
                    <div className="p-6 space-y-6">
                        {/* User ID */}
                        <div className="flex items-center space-x-4 pb-4 border-b border-gray-200">
                            <div className="w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center">
                                <User size={20} className="text-gray-600" />
                            </div>
                            <div className="flex-1">
                                <p className="text-sm text-gray-500 mb-1">사용자 ID</p>
                                <p className="text-gray-800 font-medium">
                                    {userId || 'ID 정보 없음'}
                                </p>
                            </div>
                        </div>

                        {/* Email */}
                        <div className="flex items-center space-x-4 pb-4 border-b border-gray-200">
                            <div className="w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center">
                                <Mail size={20} className="text-gray-600" />
                            </div>
                            <div className="flex-1">
                                <p className="text-sm text-gray-500 mb-1">이메일</p>
                                <p className="text-gray-800 font-medium">
                                    {userEmail || '이메일 정보 없음'}
                                </p>
                            </div>
                        </div>

                        {/* Account Actions */}
                        <div className="pt-4 space-y-3">
                            <button
                                className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition font-medium"
                            >
                                <Settings size={20} />
                                <span>설정</span>
                            </button>
                            <button
                                onClick={handleLogout}
                                className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition font-medium"
                            >
                                <LogOut size={20} />
                                <span>로그아웃</span>
                            </button>
                        </div>
                    </div>
                </div>

                {/* Additional Information */}
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                    <h3 className="text-lg font-bold text-gray-800 mb-4">계정 정보</h3>
                    <div className="space-y-3 text-sm text-gray-600">
                        <p>계정 관리를 위해 필요한 정보입니다.</p>
                        <p className="text-xs text-gray-500">
                            추가 기능은 추후 업데이트 예정입니다.
                        </p>
                    </div>
                </div>
            </main>
        </div>
    );
}

