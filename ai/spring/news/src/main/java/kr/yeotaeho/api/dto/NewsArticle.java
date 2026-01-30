package kr.yeotaeho.api.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class NewsArticle {
    private String type;
    private String title;
    private String date;
    private String image;
    private String link;
    private String description;
}

