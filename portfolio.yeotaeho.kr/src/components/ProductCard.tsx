"use client";

import React from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { motion } from 'framer-motion';

export interface ProductCardData {
    id: string;
    title: string;
    category: string;
    description: string;
    image?: string;
    imageAlt?: string;
    link?: string;
}

interface ProductCardProps {
    product: ProductCardData;
    index: number;
}

/**
 * 제품 카드 컴포넌트
 */
const ProductCard: React.FC<ProductCardProps> = ({ product, index }) => {
    const cardContent = (
        <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.5, delay: index * 0.1 }}
            className="group relative bg-white rounded-lg overflow-hidden shadow-sm hover:shadow-lg transition-shadow duration-300"
        >
            {/* 이미지 영역 */}
            <div className="relative w-full h-64 bg-gray-100 overflow-hidden">
                {product.image ? (
                    <Image
                        src={product.image}
                        alt={product.imageAlt || product.title}
                        fill
                        className="object-cover group-hover:scale-105 transition-transform duration-300"
                        sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
                    />
                ) : (
                    <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-gray-100 to-gray-200">
                        <span className="text-gray-400 text-4xl">🏥</span>
                    </div>
                )}
            </div>

            {/* 콘텐츠 영역 */}
            <div className="p-6">
                <div className="text-xs font-semibold tracking-widest text-orange-600 uppercase mb-2">
                    {product.category}
                </div>
                <h3 className="text-xl font-bold text-gray-900 mb-2 group-hover:text-orange-600 transition-colors">
                    {product.title}
                </h3>
                <p className="text-sm text-gray-600 leading-relaxed">
                    {product.description}
                </p>
            </div>

            {/* 호버 오버레이 */}
            <div className="absolute inset-0 bg-orange-600/0 group-hover:bg-orange-600/5 transition-colors duration-300 pointer-events-none"></div>
        </motion.div>
    );

    if (product.link) {
        return (
            <Link href={product.link} className="block">
                {cardContent}
            </Link>
        );
    }

    return cardContent;
};

export default ProductCard;

